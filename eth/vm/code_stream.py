import contextlib
import logging
from typing import (
    Iterator,
    Set,
    Optional,
    Dict,
    List,
)

from eth_typing import (
    Address,
)
from eth_utils.toolz import dicttoolz

from eth.abc import CodeStreamAPI
from eth.validation import (
    validate_is_bytes,
)
from eth.vm.opcode_values import (
    PUSH1,
    PUSH32,
    STOP,
)


class CodeReads:
    def __init__(self, address, reads, code_size):
        self.address: Address = address
        self.reads: Set[int] = reads
        self.code_size: int = code_size

    def __add__(self, other: "CodeReads"):
        if self.address != other.address:
            raise NotImplemented('in order to add two CodeReads their addresses must match')

        return CodeReads(
            self.address,
            self.reads | other.reads,
            self.code_size,
        )


class CodeReadsDict:
    def __init__(self, dictionary=None):
        self.dict: Dict[Address, CodeReads] = dictionary if dictionary else dict()

    def __add__(self, other: "CodeReadsDict"):
        def merge(codereads: List[CodeReads]):
            result = codereads[0]
            for read in codereads[0:]:
                result = result + read
            return result
        return CodeReadsDict(
            dicttoolz.merge_with(merge, self.dict, other.dict)
        )

    def add_reads(self, code_reads: CodeReads):
        address = code_reads.address

        if address not in self.dict:
            self.dict[address] = code_reads
        else:
            self.dict[address] = self.dict[address] + code_reads

    def total_code_bytes(self) -> int:
        return sum(
            code_reads.code_size for code_reads in self.dict.values()
        )

    def total_read_bytes(self) -> int:
        return sum(
            len(code_reads.reads) for code_reads in self.dict.values()
        )


class CodeStream(CodeStreamAPI):
    __slots__ = [
        '_length_cache', '_raw_code_bytes', 'invalid_positions', 'valid_positions',
        'pc', 'read_positions', 'code_address',
    ]

    logger = logging.getLogger('eth.vm.CodeStream')

    def __init__(self, code_bytes: bytes) -> None:
        validate_is_bytes(code_bytes, title="CodeStream bytes")
        # in order to avoid method overhead when setting/accessing pc, we no longer fence
        # the pc (Program Counter) into 0 <= pc <= len(code_bytes). We now let it float free.
        # NOTE: Setting pc to a negative value has undefined behavior.
        self.program_counter = 0
        self._raw_code_bytes = code_bytes
        self._length_cache = len(code_bytes)
        self.invalid_positions: Set[int] = set()
        self.valid_positions: Set[int] = set()

        self.read_positions: Set[int] = set()
        self.code_address: Address = None

    @property
    def code_reads(self) -> Optional[CodeReads]:
        if self.code_address is None:
            return None

        return CodeReads(
            self.code_address,
            self.read_positions,
            len(self)
        )

    def read(self, size: int) -> bytes:
        old_program_counter = self.program_counter
        target_program_counter = old_program_counter + size
        self.program_counter = target_program_counter

        for i in range(old_program_counter, target_program_counter):
            self.read_positions.add(i)

        return self._raw_code_bytes[old_program_counter:target_program_counter]

    def __len__(self) -> int:
        return self._length_cache

    def __getitem__(self, i: int) -> int:
        self.read_positions.add(i)
        return self._raw_code_bytes[i]

    def __iter__(self) -> Iterator[int]:
        # a very performance-sensitive method
        pc = self.program_counter
        while pc < self._length_cache:
            self.read_positions.add(pc)
            opcode = self._raw_code_bytes[pc]
            self.program_counter = pc + 1
            yield opcode
            # a read might have adjusted the pc during the last yield
            pc = self.program_counter

        yield STOP

    def peek(self) -> int:
        pc = self.program_counter
        if pc < self._length_cache:
            self.read_positions.add(pc)
            return self._raw_code_bytes[pc]
        else:
            return STOP

    @contextlib.contextmanager
    def seek(self, program_counter: int) -> Iterator['CodeStream']:
        anchor_pc = self.program_counter
        self.program_counter = program_counter
        try:
            yield self
        finally:
            self.program_counter = anchor_pc

    def _potentially_disqualifying_opcode_positions(self, position: int) -> Iterator[int]:
        # Look at the last 32 positions (from 1 byte back to 32 bytes back).
        # Don't attempt to look at negative positions.
        deepest_lookback = min(32, position)
        # iterate in reverse, because PUSH32 is more common than others
        for bytes_back in range(deepest_lookback, 0, -1):
            earlier_position = position - bytes_back
            opcode = self._raw_code_bytes[earlier_position]
            if PUSH1 + (bytes_back - 1) <= opcode <= PUSH32:
                # that PUSH1, if two bytes back, isn't disqualifying
                # PUSH32 in any of the bytes back is disqualifying
                yield earlier_position

    def is_valid_opcode(self, position: int) -> bool:
        if position >= self._length_cache:
            return False
        elif position in self.invalid_positions:
            return False
        elif position in self.valid_positions:
            return True
        else:
            # An opcode is not valid, iff it is the "data" following a PUSH_
            # So we look at the previous 32 bytes (PUSH32 being the largest) to see if there
            # is a PUSH_ before the opcode in this position.
            for disqualifier in self._potentially_disqualifying_opcode_positions(position):
                # Now that we found a PUSH_ before this position, we check if *that* PUSH is valid
                if self.is_valid_opcode(disqualifier):
                    # If the PUSH_ valid, then the current position is invalid
                    self.invalid_positions.add(position)
                    return False
                # Otherwise, keep looking for other potentially disqualifying PUSH_ codes

            # We didn't find any valid PUSH_ opcodes in the 32 bytes before position; it's valid
            self.valid_positions.add(position)
            return True
