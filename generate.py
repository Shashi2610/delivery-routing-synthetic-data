import argparse

from generator.config import DEFAULT_SEED, SCALES


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the synthetic delivery-routing dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scale", choices=sorted(SCALES), default="starter")
    return parser.parse_args()


def main():
    parse_args()


if __name__ == "__main__":
    main()
