#!/usr/bin/env python

import argparse
import logging

import lmdb


def main(args):
    print(args.db)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    parser = argparse.ArgumentParser(
        description="Utilities to read from the TurboGeth database"
    )
    parser.add_argument('-db', type=str, required=True)
    args = parser.parse_args()

    """
    subparsers = parser.add_subparsers(dest="command", title="subcommands")

    read_parser = subparsers.add_parser(
        'read',
    )
    """

    main(args)
