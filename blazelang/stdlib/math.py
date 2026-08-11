"""BlazeLang mathematical functions and constants."""

import math
import sys
import random as _random
from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


def _number(value, name="value"):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlazeRuntimeError(f"Math.{name} must be a number")
    return value


def _integer(value, name="value"):
    value = _number(value, name)
    if isinstance(value, float) and not value.is_integer():
        raise BlazeRuntimeError(f"Math.{name} must be a whole number")
    return int(value)


class MathLibrary:
    # ---- basic ----
    def abs(self, value): return abs(_number(value))

    def sqrt(self, value):
        value = _number(value)
        if value < 0: raise BlazeRuntimeError("Math.Sqrt cannot use a negative number")
        return math.sqrt(value)

    def cbrt(self, value):
        value = _number(value)
        return math.copysign(abs(value) ** (1 / 3), value)

    def pow(self, base, exponent): return math.pow(_number(base, "base"), _number(exponent, "exponent"))

    def sign(self, value):
        value = _number(value)
        if value > 0: return 1
        if value < 0: return -1
        return 0

    def trunc(self, value): return math.trunc(_number(value))

    # ---- trigonometry ----
    def sin(self, value): return math.sin(_number(value))
    def cos(self, value): return math.cos(_number(value))
    def tan(self, value): return math.tan(_number(value))

    def asin(self, value):
        value = _number(value)
        if value < -1 or value > 1: raise BlazeRuntimeError("Math.Asin value must be between -1 and 1")
        return math.asin(value)

    def acos(self, value):
        value = _number(value)
        if value < -1 or value > 1: raise BlazeRuntimeError("Math.Acos value must be between -1 and 1")
        return math.acos(value)

    def atan(self, value): return math.atan(_number(value))
    def atan2(self, y, x): return math.atan2(_number(y, "y"), _number(x, "x"))

    def sinh(self, value): return math.sinh(_number(value))
    def cosh(self, value): return math.cosh(_number(value))
    def tanh(self, value): return math.tanh(_number(value))

    def degrees(self, value): return math.degrees(_number(value))
    def radians(self, value): return math.radians(_number(value))

    # ---- logarithms / exponents ----
    def log(self, value, base=None):
        value = _number(value)
        if value <= 0: raise BlazeRuntimeError("Math.Log value must be greater than 0")
        if base is None: return math.log(value)
        base = _number(base, "base")
        if base <= 0 or base == 1: raise BlazeRuntimeError("Math.Log base must be greater than 0 and not equal to 1")
        return math.log(value, base)

    def log10(self, value):
        value = _number(value)
        if value <= 0: raise BlazeRuntimeError("Math.Log10 value must be greater than 0")
        return math.log10(value)

    def log2(self, value):
        value = _number(value)
        if value <= 0: raise BlazeRuntimeError("Math.Log2 value must be greater than 0")
        return math.log2(value)

    def exp(self, value): return math.exp(_number(value))

    # ---- rounding ----
    def floor(self, value): return math.floor(_number(value))
    def ceil(self, value): return math.ceil(_number(value))
    def round(self, value, digits=0): return round(_number(value), int(_number(digits, "digits")))

    # ---- comparison / ranges ----
    def min(self, *values): return min(_number(value) for value in values)
    def max(self, *values): return max(_number(value) for value in values)

    def clamp(self, value, minimum, maximum):
        value, minimum, maximum = _number(value), _number(minimum, "minimum"), _number(maximum, "maximum")
        if minimum > maximum: raise BlazeRuntimeError("Math.Clamp minimum cannot exceed maximum")
        return max(minimum, min(value, maximum))

    def lerp(self, start, end, t):
        start, end, t = _number(start, "start"), _number(end, "end"), _number(t, "t")
        return start + (end - start) * t

    def hypot(self, *values): return math.hypot(*(_number(value) for value in values))

    # ---- number theory ----
    def factorial(self, value):
        value = _integer(value, "factorial")
        if value < 0: raise BlazeRuntimeError("Math.Factorial cannot use a negative number")
        return math.factorial(value)

    def gcd(self, *values):
        ints = [_integer(value, "gcd") for value in values]
        if not ints: raise BlazeRuntimeError("Math.Gcd needs at least one value")
        return math.gcd(*ints)

    def lcm(self, *values):
        ints = [_integer(value, "lcm") for value in values]
        if not ints: raise BlazeRuntimeError("Math.Lcm needs at least one value")
        return math.lcm(*ints)

    def isPrime(self, value):
        value = _integer(value, "isPrime")
        if value < 2: return False
        if value in (2, 3): return True
        if value % 2 == 0: return False
        i = 3
        while i * i <= value:
            if value % i == 0: return False
            i += 2
        return True

    def mod(self, value, divisor):
        value, divisor = _number(value), _number(divisor, "divisor")
        if divisor == 0: raise BlazeRuntimeError("Math.Mod cannot divide by 0")
        return math.fmod(value, divisor)

    # ---- statistics ----
    def sum(self, *values): return math.fsum(_number(value) for value in values)

    def mean(self, *values):
        nums = [_number(value) for value in values]
        if not nums: raise BlazeRuntimeError("Math.Mean needs at least one value")
        return math.fsum(nums) / len(nums)

    def median(self, *values):
        nums = sorted(_number(value) for value in values)
        if not nums: raise BlazeRuntimeError("Math.Median needs at least one value")
        mid = len(nums) // 2
        if len(nums) % 2 == 0:
            return (nums[mid - 1] + nums[mid]) / 2
        return nums[mid]

    # ---- checks ----
    def isNaN(self, value):
        return isinstance(value, float) and math.isnan(value)

    def isFinite(self, value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def isInteger(self, value):
        return isinstance(value, int) and not isinstance(value, bool) or (
            isinstance(value, float) and value.is_integer()
        )

    # ---- random ----
    def random(self):
        return _random.random()

    def randomInt(self, minimum, maximum):
        minimum, maximum = _integer(minimum, "minimum"), _integer(maximum, "maximum")
        if minimum > maximum: raise BlazeRuntimeError("Math.RandomInt minimum cannot exceed maximum")
        return _random.randint(minimum, maximum)

    def randomRange(self, minimum, maximum):
        minimum, maximum = _number(minimum, "minimum"), _number(maximum, "maximum")
        if minimum > maximum: raise BlazeRuntimeError("Math.RandomRange minimum cannot exceed maximum")
        return _random.uniform(minimum, maximum)

    # =====================================================================
    # Math V2.1 additions below
    # =====================================================================

    # ---- 1. basic advanced math ----
    def square(self, value): return _number(value) ** 2
    def cube(self, value): return _number(value) ** 3

    def reciprocal(self, value):
        value = _number(value)
        if value == 0: raise BlazeRuntimeError("Math.Reciprocal cannot use zero")
        return 1 / value

    def frac(self, value):
        value = _number(value)
        return abs(value) - math.floor(abs(value)) if value >= 0 else value - math.trunc(value)

    def average(self, *values):
        nums = [_number(value) for value in values]
        if not nums: raise BlazeRuntimeError("Math.Average needs at least one value")
        return math.fsum(nums) / len(nums)

    # ---- 2. additional trigonometry ----
    def sec(self, value):
        c = math.cos(_number(value))
        if c == 0: raise BlazeRuntimeError("Math.Sec is undefined at this value")
        return 1 / c

    def csc(self, value):
        s = math.sin(_number(value))
        if s == 0: raise BlazeRuntimeError("Math.Csc is undefined at this value")
        return 1 / s

    def cot(self, value):
        t = math.tan(_number(value))
        if t == 0: raise BlazeRuntimeError("Math.Cot is undefined at this value")
        return 1 / t

    def asec(self, value):
        value = _number(value)
        if value == 0: raise BlazeRuntimeError("Math.Asec cannot use zero")
        try:
            return math.acos(1 / value)
        except ValueError:
            raise BlazeRuntimeError("Math.Asec value must have absolute value >= 1")

    def acsc(self, value):
        value = _number(value)
        if value == 0: raise BlazeRuntimeError("Math.Acsc cannot use zero")
        try:
            return math.asin(1 / value)
        except ValueError:
            raise BlazeRuntimeError("Math.Acsc value must have absolute value >= 1")

    def acot(self, value):
        value = _number(value)
        if value == 0: return math.pi / 2
        return math.atan(1 / value)

    def sinDeg(self, value): return math.sin(math.radians(_number(value)))
    def cosDeg(self, value): return math.cos(math.radians(_number(value)))

    def tanDeg(self, value):
        value = _number(value)
        # Guard the classic 90/270-degree asymptotes instead of returning
        # a huge (but finite) floating-point artifact.
        remainder = value % 180
        if math.isclose(remainder, 90, abs_tol=1e-9):
            raise BlazeRuntimeError("Math.TanDeg is undefined at this value")
        return math.tan(math.radians(value))

    # ---- 3. combinatorics ----
    def combinations(self, n, r):
        n = _integer(n, "Combinations n")
        r = _integer(r, "Combinations r")
        if n < 0 or r < 0: raise BlazeRuntimeError("Math.Combinations requires non-negative whole numbers")
        if r > n: raise BlazeRuntimeError("Math.Combinations requires r <= n")
        return math.comb(n, r)

    def permutations(self, n, r):
        n = _integer(n, "Permutations n")
        r = _integer(r, "Permutations r")
        if n < 0 or r < 0: raise BlazeRuntimeError("Math.Permutations requires non-negative whole numbers")
        if r > n: raise BlazeRuntimeError("Math.Permutations requires r <= n")
        return math.perm(n, r)

    def binomial(self, n, r):
        n = _integer(n, "Binomial n")
        r = _integer(r, "Binomial r")
        if n < 0 or r < 0: raise BlazeRuntimeError("Math.Binomial requires non-negative whole numbers")
        if r > n: raise BlazeRuntimeError("Math.Binomial requires r <= n")
        return math.comb(n, r)

    # ---- 4. number theory ----
    def fibonacci(self, n):
        n = _integer(n, "Fibonacci")
        if n < 0: raise BlazeRuntimeError("Math.Fibonacci requires a non-negative whole number")
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    def factors(self, n):
        n = _integer(n, "Factors")
        if n <= 0: raise BlazeRuntimeError("Math.Factors requires a positive whole number")
        result = []
        i = 1
        while i * i <= n:
            if n % i == 0:
                result.append(i)
                if i != n // i:
                    result.append(n // i)
            i += 1
        return sorted(result)

    def primeFactors(self, n):
        n = _integer(n, "PrimeFactors")
        if n <= 0: raise BlazeRuntimeError("Math.PrimeFactors requires a positive whole number")
        result = []
        remaining = n
        divisor = 2
        while divisor * divisor <= remaining:
            while remaining % divisor == 0:
                result.append(divisor)
                remaining //= divisor
            divisor += 1
        if remaining > 1:
            result.append(remaining)
        return result

    def nextPrime(self, n):
        n = _integer(n, "NextPrime")
        candidate = n + 1
        while not self.isPrime(candidate):
            candidate += 1
        return candidate

    def isEven(self, n):
        n = _integer(n, "IsEven")
        return n % 2 == 0

    def isOdd(self, n):
        n = _integer(n, "IsOdd")
        return n % 2 != 0

    # ---- 5. statistics ----
    def mode(self, *values):
        nums = [_number(value) for value in values]
        if not nums: raise BlazeRuntimeError("Math.Mode needs at least one value")
        counts = {}
        order = []
        for value in nums:
            if value not in counts:
                counts[value] = 0
                order.append(value)
            counts[value] += 1
        highest = max(counts.values())
        modes = [value for value in order if counts[value] == highest]
        if len(modes) == 1:
            return modes[0]
        return modes

    def variance(self, *values):
        nums = [_number(value) for value in values]
        if not nums: raise BlazeRuntimeError("Math.Variance needs at least one value")
        mean_value = math.fsum(nums) / len(nums)
        return math.fsum((value - mean_value) ** 2 for value in nums) / len(nums)

    def stdDev(self, *values):
        return math.sqrt(self.variance(*values))

    def range(self, *values):
        nums = [_number(value) for value in values]
        if not nums: raise BlazeRuntimeError("Math.Range needs at least one value")
        return max(nums) - min(nums)

    # ---- 6. random utilities ----
    def randomBool(self):
        return _random.choice([True, False])

    def randomChoice(self, values):
        if not isinstance(values, list):
            raise BlazeRuntimeError("Math.RandomChoice requires an array")
        if not values:
            raise BlazeRuntimeError("Math.RandomChoice cannot choose from an empty array")
        return _random.choice(list(values))

    def randomSign(self):
        return _random.choice([1, -1])

    # ---- 7. geometry ----
    def circleArea(self, radius):
        radius = _number(radius, "CircleArea radius")
        if radius < 0: raise BlazeRuntimeError("Math.CircleArea radius cannot be negative")
        return math.pi * radius ** 2

    def circleCircumference(self, radius):
        radius = _number(radius, "CircleCircumference radius")
        if radius < 0: raise BlazeRuntimeError("Math.CircleCircumference radius cannot be negative")
        return 2 * math.pi * radius

    def rectangleArea(self, width, height):
        width = _number(width, "RectangleArea width")
        height = _number(height, "RectangleArea height")
        if width < 0 or height < 0: raise BlazeRuntimeError("Math.RectangleArea dimensions cannot be negative")
        return width * height

    def triangleArea(self, base, height):
        base = _number(base, "TriangleArea base")
        height = _number(height, "TriangleArea height")
        if base < 0 or height < 0: raise BlazeRuntimeError("Math.TriangleArea dimensions cannot be negative")
        return 0.5 * base * height

    def distance2D(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = (_number(x1, "x1"), _number(y1, "y1"), _number(x2, "x2"), _number(y2, "y2"))
        return math.hypot(x2 - x1, y2 - y1)

    def distance3D(self, x1, y1, z1, x2, y2, z2):
        x1, y1, z1, x2, y2, z2 = (
            _number(x1, "x1"), _number(y1, "y1"), _number(z1, "z1"),
            _number(x2, "x2"), _number(y2, "y2"), _number(z2, "z2"),
        )
        return math.hypot(x2 - x1, y2 - y1, z2 - z1)

    # ---- 9. vector math ----
    def _vector(self, value, name="vector"):
        if not isinstance(value, list) or not value:
            raise BlazeRuntimeError(f"Math.{name} requires a non-empty array of numbers")
        return [_number(component, name) for component in value]

    def vectorLength(self, vector):
        components = self._vector(vector, "VectorLength")
        return math.sqrt(math.fsum(component ** 2 for component in components))

    def dot(self, a, b):
        a = self._vector(a, "Dot")
        b = self._vector(b, "Dot")
        if len(a) != len(b):
            raise BlazeRuntimeError("Math.Dot vectors must have the same length")
        return math.fsum(x * y for x, y in zip(a, b))

    def cross(self, a, b):
        a = self._vector(a, "Cross")
        b = self._vector(b, "Cross")
        if len(a) != 3 or len(b) != 3:
            raise BlazeRuntimeError("Math.Cross requires 3-dimensional vectors")
        return [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]

    # =====================================================================
    # Math V3 Developer Edition additions below
    # =====================================================================

    # ---- 10. bitwise / integer utilities ----
    # NOTE on negative values (documented deliberately):
    #   * BitAnd/BitOr/BitXor/BitNot operate on Python's arbitrary-precision
    #     two's-complement representation, so negative operands behave the
    #     way they would in any language with infinite-precision integers.
    #   * BitShiftLeft/BitShiftRight accept negative *values* (arithmetic
    #     shift), but the shift *amount* must be non-negative.
    #   * BitCount, IsPowerOfTwo and NextPowerOfTwo are magnitude-based
    #     concepts. BitCount and NextPowerOfTwo reject negative input with a
    #     BlazeRuntimeError; IsPowerOfTwo simply returns false for any
    #     non-positive value (matching IsPowerOfTwo(0) -> false).
    def bitAnd(self, a, b):
        a = _integer(a, "BitAnd a")
        b = _integer(b, "BitAnd b")
        return a & b

    def bitOr(self, a, b):
        a = _integer(a, "BitOr a")
        b = _integer(b, "BitOr b")
        return a | b

    def bitXor(self, a, b):
        a = _integer(a, "BitXor a")
        b = _integer(b, "BitXor b")
        return a ^ b

    def bitNot(self, value):
        value = _integer(value, "BitNot")
        return ~value

    def bitShiftLeft(self, value, bits):
        value = _integer(value, "BitShiftLeft value")
        bits = _integer(bits, "BitShiftLeft bits")
        if bits < 0:
            raise BlazeRuntimeError("Math.BitShiftLeft shift amount cannot be negative")
        return value << bits

    def bitShiftRight(self, value, bits):
        value = _integer(value, "BitShiftRight value")
        bits = _integer(bits, "BitShiftRight bits")
        if bits < 0:
            raise BlazeRuntimeError("Math.BitShiftRight shift amount cannot be negative")
        return value >> bits

    def bitCount(self, value):
        value = _integer(value, "BitCount")
        if value < 0:
            raise BlazeRuntimeError("Math.BitCount requires a non-negative whole number")
        return bin(value).count("1")

    def isPowerOfTwo(self, value):
        value = _integer(value, "IsPowerOfTwo")
        if value <= 0:
            return False
        return (value & (value - 1)) == 0

    def nextPowerOfTwo(self, value):
        value = _integer(value, "NextPowerOfTwo")
        if value < 0:
            raise BlazeRuntimeError("Math.NextPowerOfTwo requires a non-negative whole number")
        if value == 0:
            return 1
        if self.isPowerOfTwo(value):
            return value
        return 1 << value.bit_length()

    # ---- 11. numeric comparison / floating-point utilities ----
    def isApproximately(self, a, b, epsilon=None):
        a = _number(a, "IsApproximately a")
        b = _number(b, "IsApproximately b")
        if epsilon is None:
            return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
        epsilon = _number(epsilon, "IsApproximately epsilon")
        if epsilon < 0:
            raise BlazeRuntimeError("Math.IsApproximately epsilon cannot be negative")
        return abs(a - b) <= epsilon

    def epsilon(self):
        return sys.float_info.epsilon

    def normalize(self, value, minimum, maximum):
        value = _number(value, "Normalize value")
        minimum = _number(minimum, "Normalize minimum")
        maximum = _number(maximum, "Normalize maximum")
        if maximum == minimum:
            raise BlazeRuntimeError("Math.Normalize cannot use a zero-width range")
        return (value - minimum) / (maximum - minimum)

    def map(self, value, inMin, inMax, outMin, outMax):
        value = _number(value, "Map value")
        inMin = _number(inMin, "Map inMin")
        inMax = _number(inMax, "Map inMax")
        outMin = _number(outMin, "Map outMin")
        outMax = _number(outMax, "Map outMax")
        if inMax == inMin:
            raise BlazeRuntimeError("Math.Map input range cannot have equal endpoints")
        t = (value - inMin) / (inMax - inMin)
        return outMin + t * (outMax - outMin)

    def saturate(self, value):
        value = _number(value, "Saturate")
        return max(0, min(value, 1))

    def wrap(self, value, minimum, maximum):
        value = _number(value, "Wrap value")
        minimum = _number(minimum, "Wrap minimum")
        maximum = _number(maximum, "Wrap maximum")
        if minimum >= maximum:
            raise BlazeRuntimeError("Math.Wrap minimum must be less than maximum")
        span = maximum - minimum
        return minimum + (value - minimum) % span

    # ---- 12. interpolation ----
    def inverseLerp(self, a, b, value):
        a = _number(a, "InverseLerp a")
        b = _number(b, "InverseLerp b")
        value = _number(value, "InverseLerp value")
        if a == b:
            raise BlazeRuntimeError("Math.InverseLerp cannot use equal endpoints")
        return (value - a) / (b - a)

    def smoothStep(self, edge0, edge1, x):
        edge0 = _number(edge0, "SmoothStep edge0")
        edge1 = _number(edge1, "SmoothStep edge1")
        x = _number(x, "SmoothStep x")
        if edge0 == edge1:
            raise BlazeRuntimeError("Math.SmoothStep edges cannot be equal")
        t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
        return t * t * (3 - 2 * t)

    def smootherStep(self, edge0, edge1, x):
        edge0 = _number(edge0, "SmootherStep edge0")
        edge1 = _number(edge1, "SmootherStep edge1")
        x = _number(x, "SmootherStep x")
        if edge0 == edge1:
            raise BlazeRuntimeError("Math.SmootherStep edges cannot be equal")
        t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
        return t * t * t * (t * (t * 6 - 15) + 10)

    # ---- 13. easing functions (t normally operates in [0, 1]) ----
    def easeInQuad(self, t):
        t = _number(t, "EaseInQuad")
        return t * t

    def easeOutQuad(self, t):
        t = _number(t, "EaseOutQuad")
        return t * (2 - t)

    def easeInOutQuad(self, t):
        t = _number(t, "EaseInOutQuad")
        if t < 0.5:
            return 2 * t * t
        return -1 + (4 - 2 * t) * t

    def easeInCubic(self, t):
        t = _number(t, "EaseInCubic")
        return t ** 3

    def easeOutCubic(self, t):
        t = _number(t, "EaseOutCubic")
        shifted = t - 1
        return shifted ** 3 + 1

    def easeInOutCubic(self, t):
        t = _number(t, "EaseInOutCubic")
        if t < 0.5:
            return 4 * t ** 3
        return (t - 1) * (2 * t - 2) ** 2 + 1

    def easeInSine(self, t):
        t = _number(t, "EaseInSine")
        return 1 - math.cos(t * math.pi / 2)

    def easeOutSine(self, t):
        t = _number(t, "EaseOutSine")
        return math.sin(t * math.pi / 2)

    def easeInOutSine(self, t):
        t = _number(t, "EaseInOutSine")
        return -(math.cos(math.pi * t) - 1) / 2

    # ---- 14. modular arithmetic ----
    def modPow(self, base, exponent, modulus):
        base = _integer(base, "ModPow base")
        exponent = _integer(exponent, "ModPow exponent")
        modulus = _integer(modulus, "ModPow modulus")
        if modulus == 0:
            raise BlazeRuntimeError("Math.ModPow modulus cannot be zero")
        if exponent < 0:
            raise BlazeRuntimeError("Math.ModPow exponent must be a non-negative whole number")
        return pow(base, exponent, modulus)

    def _extendedGcd(self, a, b):
        old_r, r = a, b
        old_s, s = 1, 0
        old_t, t = 0, 1
        while r != 0:
            q = old_r // r
            old_r, r = r, old_r - q * r
            old_s, s = s, old_s - q * s
            old_t, t = t, old_t - q * t
        return old_r, old_s, old_t

    def extendedGcd(self, a, b):
        a = _integer(a, "ExtendedGcd a")
        b = _integer(b, "ExtendedGcd b")
        g, x, y = self._extendedGcd(a, b)
        return [g, x, y]

    def modInverse(self, a, modulus):
        a = _integer(a, "ModInverse a")
        modulus = _integer(modulus, "ModInverse modulus")
        if modulus == 0:
            raise BlazeRuntimeError("Math.ModInverse modulus cannot be zero")
        g, x, _ = self._extendedGcd(a, modulus)
        if g != 1:
            raise BlazeRuntimeError("Math.ModInverse inverse does not exist")
        return x % modulus

    # ---- 15. number theory performance ----
    def isPrimeFast(self, n):
        n = _integer(n, "IsPrimeFast")
        if n < 2:
            return False
        small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
        for p in small_primes:
            if n % p == 0:
                return n == p
        d = n - 1
        r = 0
        while d % 2 == 0:
            d //= 2
            r += 1
        for a in small_primes:
            if a >= n:
                continue
            x = pow(a, d, n)
            if x == 1 or x == n - 1:
                continue
            for _ in range(r - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                return False
        return True

    def fastFibonacci(self, n):
        n = _integer(n, "FastFibonacci")
        if n < 0:
            raise BlazeRuntimeError("Math.FastFibonacci requires a non-negative whole number")
        a, b = 0, 1
        for bit in bin(n)[2:]:
            c = a * (2 * b - a)
            d = a * a + b * b
            if bit == "1":
                a, b = d, c + d
            else:
                a, b = c, d
        return a

    # ---- 16. integer utilities ----
    def absInt(self, value):
        value = _integer(value, "AbsInt")
        return abs(value)

    def bitLength(self, value):
        value = _integer(value, "BitLength")
        return abs(value).bit_length()

    def gcdExtended(self, a, b):
        # Reuses the same extended-Euclid core as ExtendedGcd.
        return self.extendedGcd(a, b)

    # ---- 17. developer conversion helpers ----
    def toRadians(self, value):
        return self.radians(value)

    def toDegrees(self, value):
        return self.degrees(value)

    def toDecibels(self, amplitude):
        amplitude = _number(amplitude, "ToDecibels")
        if amplitude <= 0:
            raise BlazeRuntimeError("Math.ToDecibels amplitude must be greater than 0")
        return 20 * math.log10(amplitude)

    def fromDecibels(self, decibels):
        decibels = _number(decibels, "FromDecibels")
        return 10 ** (decibels / 20)

    # ---- 18. matrices ----
    def _matrix(self, value, name="matrix"):
        if not isinstance(value, list) or not value:
            raise BlazeRuntimeError(f"Math.{name} requires a non-empty array of arrays")
        width = None
        rows = []
        for row in value:
            if not isinstance(row, list) or not row:
                raise BlazeRuntimeError(f"Math.{name} rows must be non-empty arrays")
            if width is None:
                width = len(row)
            elif len(row) != width:
                raise BlazeRuntimeError(f"Math.{name} matrix must be rectangular")
            rows.append([_number(item, name) for item in row])
        return rows

    def _matrixDims(self, matrix):
        return len(matrix), len(matrix[0])

    def matrixAdd(self, a, b):
        a = self._matrix(a, "MatrixAdd")
        b = self._matrix(b, "MatrixAdd")
        ra, ca = self._matrixDims(a)
        rb, cb = self._matrixDims(b)
        if (ra, ca) != (rb, cb):
            raise BlazeRuntimeError(
                "Math.MatrixAdd matrices must have matching dimensions:\n"
                f"left = {ra}x{ca}\nright = {rb}x{cb}"
            )
        return [[a[i][j] + b[i][j] for j in range(ca)] for i in range(ra)]

    def matrixSubtract(self, a, b):
        a = self._matrix(a, "MatrixSubtract")
        b = self._matrix(b, "MatrixSubtract")
        ra, ca = self._matrixDims(a)
        rb, cb = self._matrixDims(b)
        if (ra, ca) != (rb, cb):
            raise BlazeRuntimeError(
                "Math.MatrixSubtract matrices must have matching dimensions:\n"
                f"left = {ra}x{ca}\nright = {rb}x{cb}"
            )
        return [[a[i][j] - b[i][j] for j in range(ca)] for i in range(ra)]

    def matrixMultiply(self, a, b):
        a = self._matrix(a, "MatrixMultiply")
        b = self._matrix(b, "MatrixMultiply")
        ra, ca = self._matrixDims(a)
        rb, cb = self._matrixDims(b)
        if ca != rb:
            raise BlazeRuntimeError(
                "Math.MatrixMultiply matrices have incompatible dimensions:\n"
                f"left = {ra}x{ca}\nright = {rb}x{cb}"
            )
        return [
            [sum(a[i][k] * b[k][j] for k in range(ca)) for j in range(cb)]
            for i in range(ra)
        ]

    def matrixTranspose(self, matrix):
        m = self._matrix(matrix, "MatrixTranspose")
        r, c = self._matrixDims(m)
        return [[m[i][j] for i in range(r)] for j in range(c)]

    def matrixIdentity(self, size):
        size = _integer(size, "MatrixIdentity size")
        if size <= 0:
            raise BlazeRuntimeError("Math.MatrixIdentity size must be a positive whole number")
        return [[1 if i == j else 0 for j in range(size)] for i in range(size)]

    def matrixScale(self, matrix, scalar):
        m = self._matrix(matrix, "MatrixScale")
        scalar = _number(scalar, "MatrixScale scalar")
        return [[value * scalar for value in row] for row in m]

    def matrixDeterminant(self, matrix):
        m = self._matrix(matrix, "MatrixDeterminant")
        r, c = self._matrixDims(m)
        if r != c:
            raise BlazeRuntimeError(
                f"Math.MatrixDeterminant requires a square matrix:\nsize = {r}x{c}"
            )
        work = [row[:] for row in m]
        n = r
        det = 1
        for i in range(n):
            pivot_row = None
            for k in range(i, n):
                if work[k][i] != 0:
                    pivot_row = k
                    break
            if pivot_row is None:
                return 0
            if pivot_row != i:
                work[i], work[pivot_row] = work[pivot_row], work[i]
                det *= -1
            det *= work[i][i]
            pivot = work[i][i]
            for k in range(i + 1, n):
                factor = work[k][i] / pivot
                for j in range(i, n):
                    work[k][j] -= factor * work[i][j]
        if isinstance(det, float) and math.isclose(det, round(det), abs_tol=1e-9):
            det = round(det)
        return det

    def matrixTrace(self, matrix):
        m = self._matrix(matrix, "MatrixTrace")
        r, c = self._matrixDims(m)
        if r != c:
            raise BlazeRuntimeError(f"Math.MatrixTrace requires a square matrix:\nsize = {r}x{c}")
        return sum(m[i][i] for i in range(r))

    # ---- 19. vector utilities ----
    def vectorAdd(self, a, b):
        a = self._vector(a, "VectorAdd")
        b = self._vector(b, "VectorAdd")
        if len(a) != len(b):
            raise BlazeRuntimeError("Math.VectorAdd vectors must have the same length")
        return [x + y for x, y in zip(a, b)]

    def vectorSubtract(self, a, b):
        a = self._vector(a, "VectorSubtract")
        b = self._vector(b, "VectorSubtract")
        if len(a) != len(b):
            raise BlazeRuntimeError("Math.VectorSubtract vectors must have the same length")
        return [x - y for x, y in zip(a, b)]

    def vectorScale(self, vector, scalar):
        vector = self._vector(vector, "VectorScale")
        scalar = _number(scalar, "VectorScale scalar")
        return [x * scalar for x in vector]

    def vectorNormalize(self, vector):
        vector = self._vector(vector, "VectorNormalize")
        length = math.sqrt(math.fsum(x ** 2 for x in vector))
        if length == 0:
            raise BlazeRuntimeError("Math.VectorNormalize cannot normalize a zero vector")
        return [x / length for x in vector]

    def vectorDistance(self, a, b):
        a = self._vector(a, "VectorDistance")
        b = self._vector(b, "VectorDistance")
        if len(a) != len(b):
            raise BlazeRuntimeError("Math.VectorDistance vectors must have the same length")
        return math.hypot(*(x - y for x, y in zip(a, b)))

    # ---- 20. angle utilities ----
    def angleBetween(self, a, b):
        a = self._vector(a, "AngleBetween")
        b = self._vector(b, "AngleBetween")
        if len(a) != len(b):
            raise BlazeRuntimeError("Math.AngleBetween vectors must have the same length")
        dot = math.fsum(x * y for x, y in zip(a, b))
        lenA = math.sqrt(math.fsum(x ** 2 for x in a))
        lenB = math.sqrt(math.fsum(x ** 2 for x in b))
        if lenA == 0 or lenB == 0:
            raise BlazeRuntimeError("Math.AngleBetween cannot use a zero vector")
        cosine = max(-1.0, min(1.0, dot / (lenA * lenB)))
        return math.acos(cosine)

    def angleBetweenDeg(self, a, b):
        return math.degrees(self.angleBetween(a, b))

    # ---- 21. range / wrapping utilities ----
    def wrap01(self, value):
        value = _number(value, "Wrap01")
        return value % 1.0

    def clamp01(self, value):
        value = _number(value, "Clamp01")
        return max(0, min(value, 1))


def create_math_module():
    library = MathLibrary()
    return {
        # ======================== Constants ========================
        "PI": math.pi,
        "E": math.e,
        "TAU": math.tau,
        "INFINITY": math.inf,
        "NAN": math.nan,
        "PHI": (1 + math.sqrt(5)) / 2,
        "SQRT2": math.sqrt(2),
        "SQRT3": math.sqrt(3),
        "LN2": math.log(2),
        "LN10": math.log(10),
        "LOG2E": 1 / math.log(2),
        "LOG10E": 1 / math.log(10),

        "EPSILON": sys.float_info.epsilon,
        "MAX_INT": sys.maxsize,
        "MIN_INT": -sys.maxsize - 1,
        "MAX_FLOAT": sys.float_info.max,
        "MIN_FLOAT": sys.float_info.min,

        # ======================== Basic ========================
        "Abs": library.abs,
        "Sqrt": library.sqrt,
        "Cbrt": library.cbrt,
        "Pow": library.pow,
        "Sign": library.sign,
        "Trunc": library.trunc,

        # ======================== Trigonometry ========================
        "Sin": library.sin,
        "Cos": library.cos,
        "Tan": library.tan,
        "Asin": library.asin,
        "Acos": library.acos,
        "Atan": library.atan,
        "Atan2": library.atan2,
        "Sinh": library.sinh,
        "Cosh": library.cosh,
        "Tanh": library.tanh,
        "Degrees": library.degrees,
        "Radians": library.radians,

        # ======================== Logarithms ========================
        "Log": library.log,
        "Log10": library.log10,
        "Log2": library.log2,
        "Exp": library.exp,

        # ======================== Rounding ========================
        "Floor": library.floor,
        "Ceil": library.ceil,
        "Round": library.round,

        # ======================== Comparison ========================
        "Min": library.min,
        "Max": library.max,
        "Clamp": library.clamp,
        "Lerp": library.lerp,
        "Hypot": library.hypot,

        # ======================== Number Theory ========================
        "Factorial": library.factorial,
        "Gcd": library.gcd,
        "Lcm": library.lcm,
        "IsPrime": library.isPrime,
        "Mod": library.mod,

        # ======================== Statistics ========================
        "Sum": library.sum,
        "Mean": library.mean,
        "Median": library.median,

        "IsNaN": library.isNaN,
        "IsFinite": library.isFinite,
        "IsInteger": library.isInteger,

        # ======================== Random ========================
        "Random": library.random,
        "RandomInt": library.randomInt,
        "RandomRange": library.randomRange,

        # ---- V2.1 additions ----
        "Square": library.square,
        "Cube": library.cube,
        "Reciprocal": library.reciprocal,
        "Frac": library.frac,
        "Average": library.average,

        "Sec": library.sec,
        "Csc": library.csc,
        "Cot": library.cot,
        "Asec": library.asec,
        "Acsc": library.acsc,
        "Acot": library.acot,
        "SinDeg": library.sinDeg,
        "CosDeg": library.cosDeg,
        "TanDeg": library.tanDeg,

        "Combinations": library.combinations,
        "Permutations": library.permutations,
        "Binomial": library.binomial,

        "Fibonacci": library.fibonacci,
        "Factors": library.factors,
        "PrimeFactors": library.primeFactors,
        "NextPrime": library.nextPrime,
        "IsEven": library.isEven,
        "IsOdd": library.isOdd,

        "Mode": library.mode,
        "Variance": library.variance,
        "StdDev": library.stdDev,
        "Range": library.range,

        "RandomBool": library.randomBool,
        "RandomChoice": library.randomChoice,
        "RandomSign": library.randomSign,

        "CircleArea": library.circleArea,
        "CircleCircumference": library.circleCircumference,
        "RectangleArea": library.rectangleArea,
        "TriangleArea": library.triangleArea,
        "Distance2D": library.distance2D,
        "Distance3D": library.distance3D,

        "VectorLength": library.vectorLength,
        "Dot": library.dot,
        "Cross": library.cross,

        # =====================================================================
        # Math V3 Developer Edition additions
        # =====================================================================

        # ======================== Developer Numeric Utilities ========================
        "IsApproximately": library.isApproximately,
        "Epsilon": library.epsilon,
        "Normalize": library.normalize,
        "Map": library.map,
        "Saturate": library.saturate,
        "Wrap": library.wrap,
        "Wrap01": library.wrap01,
        "Clamp01": library.clamp01,
        "AbsInt": library.absInt,
        "BitLength": library.bitLength,
        "GcdExtended": library.gcdExtended,

        # ======================== Bitwise ========================
        "BitAnd": library.bitAnd,
        "BitOr": library.bitOr,
        "BitXor": library.bitXor,
        "BitNot": library.bitNot,
        "BitShiftLeft": library.bitShiftLeft,
        "BitShiftRight": library.bitShiftRight,
        "BitCount": library.bitCount,
        "IsPowerOfTwo": library.isPowerOfTwo,
        "NextPowerOfTwo": library.nextPowerOfTwo,

        # ======================== Interpolation ========================
        "InverseLerp": library.inverseLerp,
        "SmoothStep": library.smoothStep,
        "SmootherStep": library.smootherStep,

        # ======================== Easing ========================
        "EaseInQuad": library.easeInQuad,
        "EaseOutQuad": library.easeOutQuad,
        "EaseInOutQuad": library.easeInOutQuad,
        "EaseInCubic": library.easeInCubic,
        "EaseOutCubic": library.easeOutCubic,
        "EaseInOutCubic": library.easeInOutCubic,
        "EaseInSine": library.easeInSine,
        "EaseOutSine": library.easeOutSine,
        "EaseInOutSine": library.easeInOutSine,

        # ======================== Modular Arithmetic ========================
        "ModPow": library.modPow,
        "ModInverse": library.modInverse,
        "ExtendedGcd": library.extendedGcd,

        # ---- Fast number theory (kept alongside existing Number Theory section) ----
        "IsPrimeFast": library.isPrimeFast,
        "FastFibonacci": library.fastFibonacci,

        # ======================== Geometry (conversions) ========================
        "ToRadians": library.toRadians,
        "ToDegrees": library.toDegrees,
        "ToDecibels": library.toDecibels,
        "FromDecibels": library.fromDecibels,

        # ======================== Vectors ========================
        "VectorAdd": library.vectorAdd,
        "VectorSubtract": library.vectorSubtract,
        "VectorScale": library.vectorScale,
        "VectorNormalize": library.vectorNormalize,
        "VectorDistance": library.vectorDistance,
        "AngleBetween": library.angleBetween,
        "AngleBetweenDeg": library.angleBetweenDeg,

        # ======================== Matrices ========================
        "MatrixAdd": library.matrixAdd,
        "MatrixSubtract": library.matrixSubtract,
        "MatrixMultiply": library.matrixMultiply,
        "MatrixTranspose": library.matrixTranspose,
        "MatrixIdentity": library.matrixIdentity,
        "MatrixScale": library.matrixScale,
        "MatrixDeterminant": library.matrixDeterminant,
        "MatrixTrace": library.matrixTrace,
    }