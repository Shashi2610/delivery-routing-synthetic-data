import numpy as np


def make_rng(seed):
    return np.random.default_rng(seed)


def pick(rng, shares, size):
    return rng.choice(list(shares), size=size, p=list(shares.values()))
