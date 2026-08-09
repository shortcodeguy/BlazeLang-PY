"""BlazeLang random-value helpers."""

import random
import secrets
import string
from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


class RandomLibrary:
    def int(self, minimum, maximum):
        if isinstance(minimum, bool) or isinstance(maximum, bool): raise BlazeRuntimeError("Random.Int bounds must be integers")
        try: return random.randint(int(minimum), int(maximum))
        except (TypeError, ValueError): raise BlazeRuntimeError("Random.Int bounds must be integers")
    def float(self): return random.random()
    def bool(self): return bool(secrets.randbits(1))
    def choice(self, values):
        if not isinstance(values, list) or not values: raise BlazeRuntimeError("Random.Choice requires a non-empty array")
        return random.choice(values)
    def shuffle(self, values):
        if not isinstance(values, list): raise BlazeRuntimeError("Random.Shuffle requires an array")
        result = list(values); random.shuffle(result); return result
    def string(self, length):
        try: length = int(length)
        except (TypeError, ValueError): raise BlazeRuntimeError("Random.String length must be a non-negative integer")
        if length < 0: raise BlazeRuntimeError("Random.String length must be a non-negative integer")
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))


def create_random_module():
    library = RandomLibrary()
    return {"Int": library.int, "Float": library.float, "Bool": library.bool,
            "Choice": library.choice, "Shuffle": library.shuffle, "String": library.string}
