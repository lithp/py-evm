#!/usr/bin/env python

import argparse
import logging

import lmdb


def main():
    pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    """
    parser = argparse.ArgumentParser(
        description="Utilities to read from the TurboGeth database"
    )
    subparsers = parser.add_subparsers(dest="command", title="subcommands")

    read_parser = subparsers.add_parser(
        'read',
    )
    """

    main()
