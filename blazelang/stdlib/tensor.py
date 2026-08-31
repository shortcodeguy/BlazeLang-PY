"""BlazeLang Tensor standard-library namespace.

Provides a multidimensional Tensor object plus creation, shape,
indexing, arithmetic, broadcasting, reduction, and linear-algebra
operations for BlazeLang runtime values.

Design notes (read this before extending):

* Storage is a **flat Python list** (`_data`) plus a `_shape` tuple and a
  `_strides` tuple (row-major / C order). This is the same layout used by
  NumPy/PyTorch internally, which keeps the door open for:
    - Autograd: each Tensor can later grow an optional `_grad` /
      `_grad_fn` slot without changing how data is stored or indexed.
    - SIMD / native backends: a flat contiguous buffer is exactly what a
      C extension, `array.array`, or a GPU upload expects -- no tree of
      nested Python lists to flatten first.
    - Neural network layers / optimizers: parameters are just Tensors,
      so a Linear layer or SGD step becomes ordinary Tensor arithmetic
      once autograd exists.
* Every operation that "changes shape but not data" (Reshape, Transpose,
  Squeeze, Unsqueeze, ExpandDims, Flatten) is implemented as new
  shape/strides over either the same or a freshly materialised flat
  buffer. Transpose uses a genuine strided view (no copy) exactly like
  NumPy, which is the right foundation for a future zero-copy autograd
  graph.
* dtype is metadata carried alongside the buffer (`_dtype`), not a
  Python-level type per element. Elements are always Python int/float;
  dtype only affects how values are coerced/rounded and what `DType`
  reports. This mirrors how `Convert` already separates "the Python
  value" from "the requested representation" and avoids duplicating
  `Convert`'s Int32/Int64/Float/String conversion logic here.
* Every op that returns a new Tensor is a pure function of its inputs --
  no operation mutates another Tensor's `_data` in place (Copy/Set are
  the only mutators, and both act on `self`). Keeping ops pure/composable
  like this is what will let a future autograd layer wrap each op with a
  `_grad_fn` node recording "how was this output produced from its
  inputs" without re-deriving that mapping later.
"""

import math
import random as _random
from typing import Any, List, Optional, Sequence, Tuple, Union

from blazelang.errors.error_handler import ValueError as BlazeValueError
from blazelang.errors.error_handler import TypeError as BlazeTypeError
from blazelang.errors.error_handler import IndexError as BlazeIndexError


# === dtype metadata ===

_SUPPORTED_DTYPES = ('float32', 'float64', 'int32', 'int64')

_DTYPE_RANGES = {
    'int32': (-2147483648, 2147483647),
    'int64': (-9223372036854775808, 9223372036854775807),
}

_DTYPE_DEFAULT = 'float64'


def _is_int_dtype(dtype: str) -> bool:
    return dtype in ('int32', 'int64')


def _coerce_scalar(value: Any, dtype: str) -> Union[int, float]:
    """Coerce a raw Python number into the representation implied by dtype."""
    if isinstance(value, bool):
        # BlazeLang booleans should not silently become 0/1 tensor data --
        # that hides a likely bug at the call site (e.g. passing a
        # condition where a number was meant).
        raise BlazeTypeError(f"Tensor elements must be numbers, got boolean")
    if not isinstance(value, (int, float)):
        raise BlazeTypeError(f"Tensor elements must be numbers, got {type(value).__name__}")
    if _is_int_dtype(dtype):
        as_int = int(value)
        low, high = _DTYPE_RANGES[dtype]
        if as_int < low or as_int > high:
            raise BlazeValueError(f"Value {as_int} does not fit in dtype '{dtype}'")
        return as_int
    # float32/float64: BlazeLang has a single Python float representation;
    # float32 is tracked as metadata only (no precision truncation is
    # performed, matching how the rest of the runtime treats numbers).
    return float(value)


def _normalize_dtype(dtype: Optional[str]) -> str:
    if dtype is None:
        return _DTYPE_DEFAULT
    if dtype not in _SUPPORTED_DTYPES:
        raise BlazeValueError(
            f"Unsupported dtype '{dtype}'. Supported dtypes: {', '.join(_SUPPORTED_DTYPES)}"
        )
    return dtype


def _infer_dtype(flat: Sequence[Any]) -> str:
    """If every element is already an int (and not a bool), default to
    int64; otherwise float64. Mixed/empty data defaults to float64."""
    if flat and all(isinstance(v, int) and not isinstance(v, bool) for v in flat):
        return 'int64'
    return _DTYPE_DEFAULT


# === shape helpers ===

def _validate_shape(shape: Sequence[Any]) -> Tuple[int, ...]:
    if not isinstance(shape, (list, tuple)):
        raise BlazeTypeError(f"Shape must be a list of integers, got {type(shape).__name__}")
    if len(shape) == 0:
        raise BlazeValueError("Shape must have at least one dimension")
    result = []
    for dim in shape:
        if isinstance(dim, bool) or not isinstance(dim, int):
            raise BlazeTypeError(f"Shape dimensions must be integers, got {type(dim).__name__}")
        if dim < 0:
            raise BlazeValueError(f"Shape dimensions must be non-negative, got {dim}")
        result.append(dim)
    return tuple(result)


def _shape_size(shape: Tuple[int, ...]) -> int:
    size = 1
    for dim in shape:
        size *= dim
    return size


def _row_major_strides(shape: Tuple[int, ...]) -> Tuple[int, ...]:
    strides = [1] * len(shape)
    for i in range(len(shape) - 2, -1, -1):
        strides[i] = strides[i + 1] * shape[i + 1]
    return tuple(strides)


def _flatten_nested(data: Any, depth: int = 0) -> Tuple[List[Any], Tuple[int, ...]]:
    """Flatten arbitrarily-nested BlazeLang lists into (flat_values, shape),
    validating that the structure is rectangular (every sub-list at a given
    depth has the same length)."""
    if not isinstance(data, list):
        return [data], ()

    if len(data) == 0:
        return [], (0,)

    first = data[0]
    if isinstance(first, list):
        sub_shapes = []
        flat: List[Any] = []
        for item in data:
            if not isinstance(item, list):
                raise BlazeValueError(
                    "Ragged tensor data: expected a nested list at every position, "
                    "but found a scalar mixed in with lists"
                )
            sub_flat, sub_shape = _flatten_nested(item, depth + 1)
            sub_shapes.append(sub_shape)
            flat.extend(sub_flat)
        if any(s != sub_shapes[0] for s in sub_shapes):
            raise BlazeValueError(
                "Ragged tensor data: all nested lists at the same depth must have the same length"
            )
        return flat, (len(data),) + sub_shapes[0]
    else:
        for item in data:
            if isinstance(item, list):
                raise BlazeValueError(
                    "Ragged tensor data: expected a scalar at every position, "
                    "but found a list mixed in with scalars"
                )
        return list(data), (len(data),)


def _broadcast_shapes(shape_a: Tuple[int, ...], shape_b: Tuple[int, ...]) -> Tuple[int, ...]:
    """NumPy-style broadcasting rule: align shapes on the right, each pair
    of dims must be equal, or one of them must be 1."""
    len_a, len_b = len(shape_a), len(shape_b)
    n = max(len_a, len_b)
    padded_a = (1,) * (n - len_a) + shape_a
    padded_b = (1,) * (n - len_b) + shape_b

    result = []
    for da, db in zip(padded_a, padded_b):
        if da == db:
            result.append(da)
        elif da == 1:
            result.append(db)
        elif db == 1:
            result.append(da)
        else:
            raise BlazeValueError(
                f"Cannot broadcast shapes {list(shape_a)} and {list(shape_b)}: "
                f"dimension {da} is incompatible with {db}"
            )
    return tuple(result)


def _broadcast_index(out_index: Tuple[int, ...], out_shape: Tuple[int, ...],
                      src_shape: Tuple[int, ...]) -> Tuple[int, ...]:
    """Map a full-rank output index down to a valid index into src_shape,
    following the same right-alignment rule as _broadcast_shapes."""
    offset = len(out_shape) - len(src_shape)
    src_index = []
    for i, dim in enumerate(src_shape):
        out_dim_index = out_index[offset + i]
        src_index.append(0 if dim == 1 else out_dim_index)
    return tuple(src_index)


def _unravel(flat_index: int, shape: Tuple[int, ...]) -> Tuple[int, ...]:
    strides = _row_major_strides(shape)
    idx = []
    remaining = flat_index
    for s in strides:
        idx.append(remaining // s if s else 0)
        remaining = remaining % s if s else 0
    return tuple(idx)


def _ravel(index: Tuple[int, ...], strides: Tuple[int, ...]) -> int:
    return sum(i * s for i, s in zip(index, strides))


def _normalize_axis(axis: int, rank: int, label: str = "axis") -> int:
    if isinstance(axis, bool) or not isinstance(axis, int):
        raise BlazeTypeError(f"{label} must be an integer, got {type(axis).__name__}")
    norm = axis + rank if axis < 0 else axis
    if norm < 0 or norm >= rank:
        raise BlazeValueError(f"{label} {axis} is out of range for rank {rank}")
    return norm


def _normalize_slice_component(value: Optional[int], default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise BlazeTypeError(f"Slice bounds must be integers, got {type(value).__name__}")
    return value


# === Tensor ===

class Tensor:
    """A multidimensional array of numbers with a fixed shape and dtype.

    Internally a flat row-major buffer + shape + strides, so that future
    work (autograd, GPU/SIMD backends, NN layers) can be layered on top
    without changing the storage model. This phase implements only plain
    Tensor semantics -- no `_grad`/`_grad_fn` machinery is wired up yet,
    but the flat-buffer + shape/strides representation, and the fact that
    every producing op is a pure function returning a new Tensor, is
    exactly what that machinery would attach to.
    """

    __slots__ = ('_data', '_shape', '_strides', '_dtype')

    def __init__(self, data: List[Any], shape: Tuple[int, ...],
                 dtype: str, strides: Optional[Tuple[int, ...]] = None):
        self._data = data
        self._shape = shape
        self._dtype = dtype
        self._strides = strides if strides is not None else _row_major_strides(shape)

    # --- construction helpers (internal) ---

    @classmethod
    def _from_flat(cls, flat: List[Any], shape: Tuple[int, ...], dtype: str) -> 'Tensor':
        dtype = _normalize_dtype(dtype)
        expected = _shape_size(shape)
        if len(flat) != expected:
            raise BlazeValueError(
                f"Data has {len(flat)} elements, which does not match shape {list(shape)} "
                f"(expects {expected})"
            )
        coerced = [_coerce_scalar(v, dtype) for v in flat]
        return cls(coerced, shape, dtype)

    def _materialize(self) -> List[Any]:
        """Return a contiguous row-major flat buffer honoring self._strides
        (needed after a Transpose, which stores a non-contiguous view)."""
        if self._strides == _row_major_strides(self._shape):
            return list(self._data)
        size = _shape_size(self._shape)
        out = [None] * size
        for flat_i in range(size):
            idx = _unravel(flat_i, self._shape)
            out[flat_i] = self._data[_ravel(idx, self._strides)]
        return out

    def _is_contiguous(self) -> bool:
        return self._strides == _row_major_strides(self._shape)

    # --- metadata ---

    @property
    def Shape(self) -> List[int]:
        return list(self._shape)

    @property
    def Rank(self) -> int:
        return len(self._shape)

    @property
    def Size(self) -> int:
        return _shape_size(self._shape)

    @property
    def DType(self) -> str:
        return self._dtype

    def __len__(self) -> int:
        return self._shape[0] if self._shape else 0

    # --- indexing (bracket protocol) ---

    def __getitem__(self, index: Any) -> Any:
        """Supports both `t[i]` (returns a sub-Tensor for rank > 1, or a
        scalar for rank 1) and `t[i, j, ...]`/`t[[i, j, ...]]` full
        multidimensional indexing in one call."""
        if isinstance(index, tuple):
            idx = list(index)
        elif isinstance(index, list):
            idx = list(index)
        else:
            idx = [index]

        if len(idx) > len(self._shape):
            raise BlazeIndexError(idx[len(self._shape)], self._shape[len(self._shape)] if len(self._shape) else 0)

        resolved = []
        for axis, i in enumerate(idx):
            dim = self._shape[axis]
            if isinstance(i, bool) or not isinstance(i, int):
                raise BlazeTypeError(f"Tensor index must be an integer, got {type(i).__name__}")
            norm = i + dim if i < 0 else i
            if norm < 0 or norm >= dim:
                raise BlazeIndexError(i, dim)
            resolved.append(norm)

        if len(resolved) == len(self._shape):
            flat_i = _ravel(tuple(resolved), self._strides)
            return self._data[flat_i]

        # Partial index -> return a sub-tensor view along the remaining axes.
        remaining_shape = self._shape[len(resolved):]
        remaining_strides = self._strides[len(resolved):]
        base_offset = sum(r * s for r, s in zip(resolved, self._strides[:len(resolved)]))

        size = _shape_size(remaining_shape)
        flat = [None] * size
        for flat_i in range(size):
            sub_idx = _unravel(flat_i, remaining_shape)
            flat[flat_i] = self._data[base_offset + _ravel(sub_idx, remaining_strides)]
        return Tensor(flat, remaining_shape, self._dtype)

    def __setitem__(self, index: Any, value: Any) -> None:
        if isinstance(index, (tuple, list)):
            idx = list(index)
        else:
            idx = [index]

        if len(idx) != len(self._shape):
            raise BlazeValueError(
                f"Tensor assignment requires a full index of length {len(self._shape)}, got {len(idx)}"
            )

        resolved = []
        for axis, i in enumerate(idx):
            dim = self._shape[axis]
            if isinstance(i, bool) or not isinstance(i, int):
                raise BlazeTypeError(f"Tensor index must be an integer, got {type(i).__name__}")
            norm = i + dim if i < 0 else i
            if norm < 0 or norm >= dim:
                raise BlazeIndexError(i, dim)
            resolved.append(norm)

        if self._strides != _row_major_strides(self._shape):
            # Writing into a non-contiguous view (e.g. after Transpose)
            # would silently mutate the original buffer's layout in a
            # confusing way -- materialize first so writes are local.
            self._data = self._materialize()
            self._strides = _row_major_strides(self._shape)

        flat_i = _ravel(tuple(resolved), self._strides)
        self._data[flat_i] = _coerce_scalar(value, self._dtype)

    # --- indexing (named method equivalents: Get / Set / Slice / Gather) ---

    def Get(self, *index: Any) -> Any:
        """Method form of `t[...]`. Accepts either separate int arguments
        (`t.Get(0, 1)`) or a single list/tuple (`t.Get([0, 1])`)."""
        if len(index) == 1 and isinstance(index[0], (list, tuple)):
            return self[list(index[0])]
        if len(index) == 1:
            return self[index[0]]
        return self[list(index)]

    def Set(self, *args: Any) -> 'Tensor':
        """Method form of `t[...] = value`. Last positional argument is the
        value; everything before it is the index. Returns self so calls can
        be chained. `t.Set(0, 1, 99)` == `t[0, 1] = 99`."""
        if len(args) < 2:
            raise BlazeValueError("Set requires an index followed by a value, e.g. Set(0, 1, 99)")
        *index_parts, value = args
        if len(index_parts) == 1 and isinstance(index_parts[0], (list, tuple)):
            self[list(index_parts[0])] = value
        else:
            self[list(index_parts)] = value
        return self

    def Slice(self, ranges: Sequence[Any]) -> 'Tensor':
        """NumPy-style basic slicing. `ranges` is a list with one entry per
        leading axis; each entry is either an int (select-and-drop-that-
        axis) or a `[start, stop, step]`/`[start, stop]`/`[start]`/`[]`
        list (a half-open range, Python `slice` semantics, negative
        indices allowed). Axes not covered by `ranges` are kept whole.
        Returns a new Tensor (materialized copy, not a view, since a
        strided slice-of-a-transpose is not expressible with a single
        stride tuple in general)."""
        if not isinstance(ranges, (list, tuple)):
            raise BlazeTypeError(f"Slice expects a list of per-axis ranges, got {type(ranges).__name__}")
        if len(ranges) > self.Rank:
            raise BlazeValueError(f"Slice has {len(ranges)} entries but tensor has rank {self.Rank}")

        py_slices = []  # one per axis: either an int, or a Python slice
        for axis, spec in enumerate(ranges):
            dim = self._shape[axis]
            if isinstance(spec, bool):
                raise BlazeTypeError("Slice entries must be an integer or a [start, stop, step] list")
            if isinstance(spec, int):
                norm = spec + dim if spec < 0 else spec
                if norm < 0 or norm >= dim:
                    raise BlazeIndexError(spec, dim)
                py_slices.append(norm)
            elif isinstance(spec, (list, tuple)):
                if len(spec) > 3:
                    raise BlazeValueError("Slice range must have at most 3 elements: [start, stop, step]")
                raw_start = spec[0] if len(spec) > 0 else None
                raw_stop = spec[1] if len(spec) > 1 else None
                raw_step = spec[2] if len(spec) > 2 else None
                step = _normalize_slice_component(raw_step, 1)
                if step == 0:
                    raise BlazeValueError("Slice step must not be zero")
                # Let Python's own slice.indices() resolve None/negative
                # start/stop against `dim` -- it already implements the
                # correct (and step-sign-dependent) defaulting rules, so
                # duplicating that logic here would just risk diverging
                # from it (as an earlier version of this code did for
                # negative-step reversal).
                if isinstance(raw_start, bool) or (raw_start is not None and not isinstance(raw_start, int)):
                    raise BlazeTypeError(f"Slice bounds must be integers, got {type(raw_start).__name__}")
                if isinstance(raw_stop, bool) or (raw_stop is not None and not isinstance(raw_stop, int)):
                    raise BlazeTypeError(f"Slice bounds must be integers, got {type(raw_stop).__name__}")
                py_slices.append(slice(raw_start, raw_stop, step))
            else:
                raise BlazeTypeError(
                    f"Slice entries must be an integer or a [start, stop, step] list, got {type(spec).__name__}"
                )

        # Remaining trailing axes are kept whole.
        for axis in range(len(ranges), self.Rank):
            py_slices.append(slice(None, None, None))

        # Resolve each axis to a concrete list of source indices, then walk
        # the cartesian product to build the output flat buffer + shape.
        axis_indices = []
        out_shape = []
        for axis, spec in enumerate(py_slices):
            dim = self._shape[axis]
            if isinstance(spec, int):
                axis_indices.append([spec])
            else:
                idxs = list(range(*spec.indices(dim)))
                axis_indices.append(idxs)
                out_shape.append(len(idxs))

        # If every axis was an int (fully collapsed), out_shape is empty --
        # represent that as a rank-1, size-1 Tensor (BlazeLang Tensors have
        # no rank-0/scalar shape) rather than folding it into whatever the
        # last non-collapsed axis happened to compute.
        flat = []

        def _walk(axis: int, prefix: Tuple[int, ...]):
            if axis == len(axis_indices):
                flat.append(self._data[_ravel(prefix, self._strides)])
                return
            for i in axis_indices[axis]:
                _walk(axis + 1, prefix + (i,))

        _walk(0, ())

        final_shape = tuple(out_shape) if out_shape else (len(flat),)
        return Tensor(flat, final_shape, self._dtype)

    def Gather(self, indices: Any, axis: int = 0) -> 'Tensor':
        """Select entries along `axis` by a list of integer indices,
        mirroring TensorFlow/PyTorch `gather`/`index_select`. Result has
        the same rank as self; `axis`'s dimension becomes len(indices)."""
        norm_axis = _normalize_axis(axis, self.Rank, "Gather axis")
        if isinstance(indices, Tensor):
            index_list = indices._materialize()
        elif isinstance(indices, (list, tuple)):
            index_list = list(indices)
        else:
            raise BlazeTypeError(f"Gather indices must be a list or Tensor, got {type(indices).__name__}")

        dim = self._shape[norm_axis]
        resolved_indices = []
        for i in index_list:
            if isinstance(i, bool) or not isinstance(i, int):
                raise BlazeTypeError(f"Gather indices must be integers, got {type(i).__name__}")
            norm = i + dim if i < 0 else i
            if norm < 0 or norm >= dim:
                raise BlazeIndexError(i, dim)
            resolved_indices.append(norm)

        out_shape = self._shape[:norm_axis] + (len(resolved_indices),) + self._shape[norm_axis + 1:]
        out_strides = _row_major_strides(out_shape)
        size = _shape_size(out_shape)
        flat = [None] * size

        for flat_i in range(size):
            out_idx = _unravel(flat_i, out_shape)
            src_idx = list(out_idx)
            src_idx[norm_axis] = resolved_indices[out_idx[norm_axis]]
            flat[flat_i] = self._data[_ravel(tuple(src_idx), self._strides)]

        return Tensor(flat, out_shape, self._dtype, strides=out_strides)

    # --- shape operations ---

    def Reshape(self, new_shape: Sequence[Any]) -> 'Tensor':
        shape = _validate_shape(new_shape)
        if _shape_size(shape) != self.Size:
            raise BlazeValueError(
                f"Cannot reshape tensor of size {self.Size} into shape {list(shape)} "
                f"(size {_shape_size(shape)})"
            )
        return Tensor(self._materialize(), shape, self._dtype)

    def Flatten(self) -> 'Tensor':
        return Tensor(self._materialize(), (self.Size,), self._dtype)

    def Transpose(self, axes: Optional[Sequence[int]] = None) -> 'Tensor':
        rank = self.Rank
        if axes is None:
            axes = list(reversed(range(rank)))
        else:
            axes = list(axes)
            if sorted(axes) != list(range(rank)):
                raise BlazeValueError(
                    f"Transpose axes {axes} must be a permutation of 0..{rank - 1}"
                )
        new_shape = tuple(self._shape[a] for a in axes)
        new_strides = tuple(self._strides[a] for a in axes)
        return Tensor(self._data, new_shape, self._dtype, strides=new_strides)

    def Squeeze(self, axis: Optional[int] = None) -> 'Tensor':
        if axis is None:
            new_shape = tuple(d for d in self._shape if d != 1)
            if not new_shape:
                new_shape = (1,)
        else:
            if axis < 0:
                axis += self.Rank
            if axis < 0 or axis >= self.Rank:
                raise BlazeValueError(f"Squeeze axis {axis} is out of range for rank {self.Rank}")
            if self._shape[axis] != 1:
                raise BlazeValueError(f"Cannot squeeze axis {axis} with size {self._shape[axis]} (must be 1)")
            new_shape = self._shape[:axis] + self._shape[axis + 1:]
            if not new_shape:
                new_shape = (1,)
        return Tensor(self._materialize(), new_shape, self._dtype)

    def Unsqueeze(self, axis: int) -> 'Tensor':
        rank = self.Rank
        if axis < 0:
            axis += rank + 1
        if axis < 0 or axis > rank:
            raise BlazeValueError(f"Unsqueeze axis {axis} is out of range for rank {rank}")
        new_shape = self._shape[:axis] + (1,) + self._shape[axis:]
        return Tensor(self._materialize(), new_shape, self._dtype)

    def ExpandDims(self, axis: int) -> 'Tensor':
        """Alias of Unsqueeze, matching the TensorFlow/NumPy naming that
        BlazeLang users coming from those libraries will expect."""
        return self.Unsqueeze(axis)

    # --- elementwise / scalar / broadcasting arithmetic ---

    def _binary_op(self, other: Any, op, op_name: str) -> 'Tensor':
        if isinstance(other, Tensor):
            out_shape = _broadcast_shapes(self._shape, other._shape)
            out_dtype = _result_dtype(self._dtype, other._dtype)
            size = _shape_size(out_shape)
            out = [None] * size
            for flat_i in range(size):
                out_idx = _unravel(flat_i, out_shape)
                a_idx = _broadcast_index(out_idx, out_shape, self._shape)
                b_idx = _broadcast_index(out_idx, out_shape, other._shape)
                a_val = self._data[_ravel(a_idx, self._strides)]
                b_val = other._data[_ravel(b_idx, other._strides)]
                out[flat_i] = op(a_val, b_val)
            return Tensor._from_flat(out, out_shape, out_dtype)

        if isinstance(other, (int, float)) and not isinstance(other, bool):
            out = [op(v, other) for v in self._materialize()]
            return Tensor._from_flat(out, self._shape, self._dtype)

        raise BlazeTypeError(f"Cannot apply '{op_name}' between Tensor and {type(other).__name__}")

    def _reflected_binary_op(self, other: Any, op, op_name: str) -> 'Tensor':
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            out = [op(other, v) for v in self._materialize()]
            return Tensor._from_flat(out, self._shape, self._dtype)
        raise BlazeTypeError(f"Cannot apply '{op_name}' between {type(other).__name__} and Tensor")

    def __add__(self, other): return self._binary_op(other, lambda a, b: a + b, '+')
    def __radd__(self, other): return self._reflected_binary_op(other, lambda a, b: a + b, '+')
    def __sub__(self, other): return self._binary_op(other, lambda a, b: a - b, '-')
    def __rsub__(self, other): return self._reflected_binary_op(other, lambda a, b: a - b, '-')
    def __mul__(self, other): return self._binary_op(other, lambda a, b: a * b, '*')
    def __rmul__(self, other): return self._reflected_binary_op(other, lambda a, b: a * b, '*')

    def __truediv__(self, other):
        def safe_div(a, b):
            if b == 0:
                raise BlazeValueError("Division by zero in tensor division")
            return a / b
        return self._binary_op(other, safe_div, '/')

    def __rtruediv__(self, other):
        def safe_div(a, b):
            if b == 0:
                raise BlazeValueError("Division by zero in tensor division")
            return a / b
        return self._reflected_binary_op(other, safe_div, '/')

    def __pow__(self, other): return self._binary_op(other, lambda a, b: a ** b, '**')

    def __neg__(self) -> 'Tensor':
        return Tensor._from_flat([-v for v in self._materialize()], self._shape, self._dtype)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Tensor):
            return NotImplemented
        return self._shape == other._shape and self._materialize() == other._materialize()

    def __hash__(self):
        return id(self)

    def __repr__(self) -> str:
        return f"Tensor(shape={list(self._shape)}, dtype={self._dtype}, data={self.ToArray()})"

    # --- named arithmetic methods (TensorFlow/PyTorch-style API surface) ---
    #
    # These are thin, explicit wrappers around the dunder-based operators
    # above so BlazeLang code can call `a.Add(b)` / `Tensor.Add(a, b)`
    # style just as readily as `a + b`. They intentionally reuse the exact
    # same `_binary_op`/`_reflected_binary_op` machinery (same broadcasting,
    # same dtype promotion, same error messages) rather than duplicating it.

    def Add(self, other: Any) -> 'Tensor':
        return self._binary_op(other, lambda a, b: a + b, 'Add')

    def Sub(self, other: Any) -> 'Tensor':
        return self._binary_op(other, lambda a, b: a - b, 'Sub')

    def Mul(self, other: Any) -> 'Tensor':
        return self._binary_op(other, lambda a, b: a * b, 'Mul')

    def Div(self, other: Any) -> 'Tensor':
        def safe_div(a, b):
            if b == 0:
                raise BlazeValueError("Division by zero in tensor division")
            return a / b
        return self._binary_op(other, safe_div, 'Div')

    def Pow(self, other: Union[int, float, 'Tensor']) -> 'Tensor':
        if isinstance(other, Tensor) or (isinstance(other, (int, float)) and not isinstance(other, bool)):
            return self._binary_op(other, lambda a, b: a ** b, 'Pow')
        raise BlazeTypeError(f"Pow exponent must be a number or Tensor, got {type(other).__name__}")

    def Hadamard(self, other: 'Tensor') -> 'Tensor':
        """Elementwise (Hadamard) product. Distinct name from Mul only to
        match the common linear-algebra term; behaves identically to Mul,
        including scalar/broadcast support -- Hadamard product IS
        elementwise multiplication, never MatMul's row-by-column sum."""
        return self._binary_op(other, lambda a, b: a * b, 'Hadamard')

    # --- reductions (axis-aware, preserving no-axis whole-tensor behavior) ---

    def _reduce_all(self, fn, empty_error: str):
        flat = self._materialize()
        if not flat:
            raise BlazeValueError(empty_error)
        return fn(flat)

    def _reduce_axis(self, axis: int, fn, empty_error: str, keepdims: bool = False) -> 'Tensor':
        norm_axis = _normalize_axis(axis, self.Rank, "Reduction axis")
        if self._shape[norm_axis] == 0:
            raise BlazeValueError(empty_error)

        out_shape_full = self._shape[:norm_axis] + (1,) + self._shape[norm_axis + 1:]
        out_shape = out_shape_full if keepdims else (
            self._shape[:norm_axis] + self._shape[norm_axis + 1:] or (1,)
        )
        reduced_shape = self._shape[:norm_axis] + self._shape[norm_axis + 1:]
        if not reduced_shape:
            reduced_shape = (1,)
        size = _shape_size(reduced_shape)
        out = [None] * size
        axis_len = self._shape[norm_axis]

        for flat_i in range(size):
            out_idx = _unravel(flat_i, reduced_shape) if reduced_shape != (1,) or self.Rank > 1 else (0,)
            if self.Rank == 1:
                # Reducing the only axis of a rank-1 tensor collapses to a
                # single value regardless of keepdims' shape bookkeeping.
                values = self._materialize()
            else:
                full_idx = list(out_idx[:norm_axis]) + [0] + list(out_idx[norm_axis:])
                values = []
                for k in range(axis_len):
                    full_idx[norm_axis] = k
                    values.append(self._data[_ravel(tuple(full_idx), self._strides)])
            out[flat_i] = fn(values)

        return _tensor_from_reduction(out, out_shape, self._dtype)

    def Sum(self, axis: Optional[int] = None, keepdims: bool = False) -> Union[int, float, 'Tensor']:
        if axis is None:
            return self._reduce_all(sum, "Cannot Sum an empty tensor")
        return self._reduce_axis(axis, sum, "Cannot Sum along an empty axis", keepdims)

    def Mean(self, axis: Optional[int] = None, keepdims: bool = False) -> Union[float, 'Tensor']:
        if axis is None:
            flat = self._materialize()
            if not flat:
                raise BlazeValueError("Cannot Mean an empty tensor")
            return sum(flat) / len(flat)
        return self._reduce_axis(axis, lambda vals: sum(vals) / len(vals), "Cannot Mean along an empty axis", keepdims)

    def Min(self, axis: Optional[int] = None, keepdims: bool = False) -> Union[int, float, 'Tensor']:
        if axis is None:
            return self._reduce_all(min, "Cannot Min an empty tensor")
        return self._reduce_axis(axis, min, "Cannot Min along an empty axis", keepdims)

    def Max(self, axis: Optional[int] = None, keepdims: bool = False) -> Union[int, float, 'Tensor']:
        if axis is None:
            return self._reduce_all(max, "Cannot Max an empty tensor")
        return self._reduce_axis(axis, max, "Cannot Max along an empty axis", keepdims)

    def ArgMin(self, axis: Optional[int] = None) -> Union[int, 'Tensor']:
        if axis is None:
            flat = self._materialize()
            if not flat:
                raise BlazeValueError("Cannot ArgMin an empty tensor")
            return min(range(len(flat)), key=lambda i: flat[i])
        result = self._reduce_axis(
            axis,
            lambda vals: min(range(len(vals)), key=lambda i: vals[i]),
            "Cannot ArgMin along an empty axis",
            keepdims=False,
        )
        # ArgMin must return int64 indices
        return Tensor._from_flat(
            [int(v) for v in result._materialize()],
            result._shape,
            "int64"
        )

    def ArgMax(self, axis: Optional[int] = None) -> Union[int, 'Tensor']:
        if axis is None:
            flat = self._materialize()
            if not flat:
                raise BlazeValueError("Cannot ArgMax an empty tensor")
            return max(range(len(flat)), key=lambda i: flat[i])
        result = self._reduce_axis(
            axis,
            lambda vals: max(range(len(vals)), key=lambda i: vals[i]),
            "Cannot ArgMax along an empty axis",
            keepdims=False,
        )
        # ArgMax must return int64 indices
        return Tensor._from_flat(
            [int(v) for v in result._materialize()],
            result._shape,
            "int64"
        )

    def Variance(self, axis: Optional[int] = None, keepdims: bool = False) -> Union[float, 'Tensor']:
        """Population variance (denominator N, matching NumPy's default ddof=0)."""
        if axis is None:
            flat = self._materialize()
            if not flat:
                raise BlazeValueError("Cannot compute Variance of an empty tensor")
            mean = sum(flat) / len(flat)
            return sum((v - mean) ** 2 for v in flat) / len(flat)

        def var_fn(vals):
            mean = sum(vals) / len(vals)
            return sum((v - mean) ** 2 for v in vals) / len(vals)

        return self._reduce_axis(axis, var_fn, "Cannot compute Variance along an empty axis", keepdims)

    def Std(self, axis: Optional[int] = None, keepdims: bool = False) -> Union[float, 'Tensor']:
        result = self.Variance(axis=axis, keepdims=keepdims)
        if isinstance(result, Tensor):
            return result.Sqrt()
        return math.sqrt(result)

    # --- linear algebra ---

    def MatMul(self, other: 'Tensor') -> 'Tensor':
        if not isinstance(other, Tensor):
            raise BlazeTypeError(f"MatMul requires a Tensor, got {type(other).__name__}")
        if self.Rank != 2 or other.Rank != 2:
            raise BlazeValueError(
                f"MatMul requires two rank-2 tensors, got ranks {self.Rank} and {other.Rank}"
            )
        m, k1 = self._shape
        k2, n = other._shape
        if k1 != k2:
            raise BlazeValueError(
                f"MatMul shape mismatch: {list(self._shape)} vs {list(other._shape)} "
                f"(inner dimensions {k1} and {k2} must match)"
            )
        a = self._materialize()
        b = other._materialize()
        out_dtype = _result_dtype(self._dtype, other._dtype)
        out = [0] * (m * n)
        for i in range(m):
            for kk in range(k1):
                a_val = a[i * k1 + kk]
                if a_val == 0:
                    continue
                row_off = kk * n
                out_off = i * n
                for j in range(n):
                    out[out_off + j] += a_val * b[row_off + j]
        return Tensor._from_flat(out, (m, n), out_dtype)

    def Dot(self, other: 'Tensor') -> Union[int, float, 'Tensor']:
        if not isinstance(other, Tensor):
            raise BlazeTypeError(f"Dot requires a Tensor, got {type(other).__name__}")
        if self.Rank == 1 and other.Rank == 1:
            if self._shape != other._shape:
                raise BlazeValueError(
                    f"Dot shape mismatch: {list(self._shape)} vs {list(other._shape)}"
                )
            a = self._materialize()
            b = other._materialize()
            return sum(x * y for x, y in zip(a, b))
        # Fall back to matrix multiplication semantics for higher ranks.
        return self.MatMul(other)

    def Norm(self, ord: Union[int, str] = 2) -> float:
        flat = self._materialize()
        if ord == 1:
            return float(sum(abs(v) for v in flat))
        if ord in (float('inf'), 'inf'):
            return float(max(abs(v) for v in flat)) if flat else 0.0
        if ord == 2:
            return math.sqrt(sum(v * v for v in flat))
        if isinstance(ord, (int, float)) and not isinstance(ord, bool):
            return sum(abs(v) ** ord for v in flat) ** (1.0 / ord)
        raise BlazeValueError(f"Unsupported norm order: {ord!r}")

    def Trace(self) -> Union[int, float]:
        """Sum of the main diagonal of a rank-2 (square or rectangular) tensor."""
        if self.Rank != 2:
            raise BlazeValueError(f"Trace requires a rank-2 tensor, got rank {self.Rank}")
        rows, cols = self._shape
        n = min(rows, cols)
        if n == 0:
            raise BlazeValueError("Cannot compute Trace of an empty matrix")
        return sum(self._data[_ravel((i, i), self._strides)] for i in range(n))

    def Diagonal(self) -> 'Tensor':
        """Main diagonal of a rank-2 tensor, as a rank-1 Tensor."""
        if self.Rank != 2:
            raise BlazeValueError(f"Diagonal requires a rank-2 tensor, got rank {self.Rank}")
        rows, cols = self._shape
        n = min(rows, cols)
        flat = [self._data[_ravel((i, i), self._strides)] for i in range(n)]
        return Tensor(flat, (n,), self._dtype)

    def Inverse(self) -> 'Tensor':
        """Matrix inverse via Gauss-Jordan elimination with partial
        pivoting. Requires a square, non-singular matrix; result dtype is
        always a float dtype (an inverse is rarely exactly representable
        in integers)."""
        if self.Rank != 2:
            raise BlazeValueError(f"Inverse requires a rank-2 tensor, got rank {self.Rank}")
        n, cols = self._shape
        if n != cols:
            raise BlazeValueError(f"Inverse requires a square matrix, got shape {list(self._shape)}")
        if n == 0:
            raise BlazeValueError("Cannot invert an empty matrix")

        # Augmented [A | I], worked in plain Python floats.
        a = self._materialize()
        aug = [[float(a[i * n + j]) for j in range(n)] + [1.0 if j == i else 0.0 for j in range(n)]
               for i in range(n)]

        for col in range(n):
            pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
            if abs(aug[pivot_row][col]) < 1e-12:
                raise BlazeValueError("Matrix is singular (or numerically too close to singular) and cannot be inverted")
            if pivot_row != col:
                aug[col], aug[pivot_row] = aug[pivot_row], aug[col]

            pivot = aug[col][col]
            aug[col] = [x / pivot for x in aug[col]]

            for r in range(n):
                if r == col:
                    continue
                factor = aug[r][col]
                if factor != 0.0:
                    aug[r] = [aug[r][k] - factor * aug[col][k] for k in range(2 * n)]

        flat = [aug[i][n + j] for i in range(n) for j in range(n)]
        return Tensor._from_flat(flat, (n, n), 'float64')

    # --- elementwise math (tensor-aware wrappers) ---

    def _elementwise(self, fn, name: str, force_float: bool = True) -> 'Tensor':
        out = []
        for v in self._materialize():
            try:
                out.append(fn(v))
            except (ValueError, OverflowError, ZeroDivisionError) as error:
                raise BlazeValueError(f"{name} is undefined for value {v}: {error}")
        result_dtype = 'float64' if (force_float and _is_int_dtype(self._dtype)) else self._dtype
        return Tensor._from_flat(out, self._shape, result_dtype)

    def Abs(self) -> 'Tensor':
        return self._elementwise(abs, 'Abs', force_float=False)

    def Sqrt(self) -> 'Tensor':
        return self._elementwise(math.sqrt, 'Sqrt')

    def Exp(self) -> 'Tensor':
        return self._elementwise(math.exp, 'Exp')

    def Log(self) -> 'Tensor':
        return self._elementwise(math.log, 'Log')

    def Sin(self) -> 'Tensor':
        return self._elementwise(math.sin, 'Sin')

    def Cos(self) -> 'Tensor':
        return self._elementwise(math.cos, 'Cos')

    def Tan(self) -> 'Tensor':
        return self._elementwise(math.tan, 'Tan')

    def Tanh(self) -> 'Tensor':
        return self._elementwise(math.tanh, 'Tanh')

    def Sigmoid(self) -> 'Tensor':
        def sigmoid(v):
            # Numerically stable form -- avoids overflow in math.exp for
            # very negative inputs by branching on the sign of v.
            if v >= 0:
                z = math.exp(-v)
                return 1.0 / (1.0 + z)
            z = math.exp(v)
            return z / (1.0 + z)
        return self._elementwise(sigmoid, 'Sigmoid')

    def ReLU(self) -> 'Tensor':
        return self._elementwise(lambda v: v if v > 0 else (0 if not _is_int_dtype(self._dtype) else 0),
                                  'ReLU', force_float=False)

    def LeakyReLU(self, alpha: float = 0.01) -> 'Tensor':
        if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
            raise BlazeTypeError(f"LeakyReLU alpha must be a number, got {type(alpha).__name__}")
        return self._elementwise(lambda v: v if v > 0 else alpha * v, 'LeakyReLU')

    def Softmax(self, axis: int = -1) -> 'Tensor':
        """Softmax along `axis` (default: last axis), numerically
        stabilized by subtracting the per-slice max before exponentiating."""
        norm_axis = _normalize_axis(axis, self.Rank, "Softmax axis")
        axis_len = self._shape[norm_axis]
        if axis_len == 0:
            raise BlazeValueError("Cannot compute Softmax along an empty axis")

        out_shape = self._shape
        out_strides = _row_major_strides(out_shape)
        out = [0.0] * _shape_size(out_shape)

        reduced_shape = self._shape[:norm_axis] + self._shape[norm_axis + 1:]
        if not reduced_shape:
            reduced_shape = (1,)
        outer_size = _shape_size(reduced_shape)

        for outer_i in range(outer_size):
            outer_idx = _unravel(outer_i, reduced_shape) if self.Rank > 1 else ()
            full_idx = list(outer_idx[:norm_axis]) + [0] + list(outer_idx[norm_axis:])

            values = []
            for k in range(axis_len):
                full_idx[norm_axis] = k
                values.append(self._data[_ravel(tuple(full_idx), self._strides)])

            m = max(values)
            exps = [math.exp(v - m) for v in values]
            total = sum(exps)
            probs = [e / total for e in exps]

            for k in range(axis_len):
                full_idx[norm_axis] = k
                out[_ravel(tuple(full_idx), out_strides)] = probs[k]

        return Tensor._from_flat(out, out_shape, 'float64')

    def Clamp(self, min: Optional[float] = None, max: Optional[float] = None) -> 'Tensor':
        if min is None and max is None:
            raise BlazeValueError("Clamp requires at least one of min/max")
        if min is not None and (isinstance(min, bool) or not isinstance(min, (int, float))):
            raise BlazeTypeError(f"Clamp min must be a number, got {type(min).__name__}")
        if max is not None and (isinstance(max, bool) or not isinstance(max, (int, float))):
            raise BlazeTypeError(f"Clamp max must be a number, got {type(max).__name__}")
        if min is not None and max is not None and min > max:
            raise BlazeValueError(f"Clamp min ({min}) must not exceed max ({max})")

        def clamp_fn(v):
            if min is not None and v < min:
                return min
            if max is not None and v > max:
                return max
            return v

        return self._elementwise(clamp_fn, 'Clamp', force_float=False)

    def Sign(self) -> 'Tensor':
        def sign_fn(v):
            if v > 0:
                return 1
            if v < 0:
                return -1
            return 0
        return self._elementwise(sign_fn, 'Sign', force_float=False)

    def Reciprocal(self) -> 'Tensor':
        def recip(v):
            if v == 0:
                raise BlazeValueError("Reciprocal is undefined for value 0")
            return 1.0 / v
        return self._elementwise(recip, 'Reciprocal')

    # --- tensor utilities ---

    def ToArray(self) -> Any:
        """Convert back into nested BlazeLang lists matching self.Shape."""
        flat = self._materialize()
        return _reshape_to_nested(flat, self._shape)

    def Copy(self) -> 'Tensor':
        """A fully independent deep copy: new flat buffer, contiguous
        strides, same shape/dtype. Mutating the copy (via Set/__setitem__)
        never affects the original, even if the original was a
        non-contiguous view (e.g. the result of Transpose)."""
        return Tensor(self._materialize(), self._shape, self._dtype)

    def IsFinite(self) -> 'Tensor':
        """Elementwise finiteness check; returns an int32 Tensor of the
        same shape with 1 where finite, 0 where NaN/Infinity."""
        out = [1 if math.isfinite(v) else 0 for v in self._materialize()]
        return Tensor._from_flat(out, self._shape, 'int32')


def _result_dtype(a: str, b: str) -> str:
    """When combining two tensors, prefer the 'wider' dtype: any float
    wins over int, and 64-bit wins over 32-bit of the same kind."""
    rank = {'int32': 0, 'int64': 1, 'float32': 2, 'float64': 3}
    return a if rank[a] >= rank[b] else b


def _reduction_result_dtype(values: Sequence[Any], base_dtype: str) -> str:
    """dtype for the *result* of an axis-aware reduction: Sum/Min/Max/ArgMin
    over an int tensor stay int; Mean/Variance/Std produce floats even from
    an int tensor (matching Mean()'s existing no-axis behavior above)."""
    if values and all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return base_dtype if _is_int_dtype(base_dtype) else _DTYPE_DEFAULT
    return 'float64' if _is_int_dtype(base_dtype) else base_dtype


def _tensor_from_reduction(flat: List[Any], shape: Tuple[int, ...], dtype: str) -> 'Tensor':
    resolved_dtype = _reduction_result_dtype(flat, dtype)
    return Tensor._from_flat(flat, shape, resolved_dtype)


def _reshape_to_nested(flat: List[Any], shape: Tuple[int, ...]) -> Any:
    if len(shape) == 0:
        return flat[0] if flat else None
    if len(shape) == 1:
        return list(flat)
    dim = shape[0]
    sub_size = _shape_size(shape[1:])
    return [
        _reshape_to_nested(flat[i * sub_size:(i + 1) * sub_size], shape[1:])
        for i in range(dim)
    ]


# === TensorLibrary (module-level factory functions) ===

class TensorLibrary:
    """Tensor creation and namespace-level operations for BlazeLang."""

    def create(self, data: Any, dtype: Optional[str] = None) -> Tensor:
        """Tensor.Create(data) -- build a Tensor from a (possibly nested)
        BlazeLang list, inferring dtype unless one is given."""
        flat, shape = _flatten_nested(data)
        if not shape:
            raise BlazeTypeError("Tensor.Create expects a list (or nested list) of numbers")
        resolved_dtype = _normalize_dtype(dtype) if dtype is not None else _infer_dtype(flat)
        return Tensor._from_flat(flat, shape, resolved_dtype)

    def zeros(self, shape: Sequence[Any], dtype: Optional[str] = None) -> Tensor:
        s = _validate_shape(shape)
        resolved_dtype = _normalize_dtype(dtype)
        fill = 0 if _is_int_dtype(resolved_dtype) else 0.0
        return Tensor([fill] * _shape_size(s), s, resolved_dtype)

    def ones(self, shape: Sequence[Any], dtype: Optional[str] = None) -> Tensor:
        s = _validate_shape(shape)
        resolved_dtype = _normalize_dtype(dtype)
        fill = 1 if _is_int_dtype(resolved_dtype) else 1.0
        return Tensor([fill] * _shape_size(s), s, resolved_dtype)

    def full(self, shape: Sequence[Any], value: Any, dtype: Optional[str] = None) -> Tensor:
        s = _validate_shape(shape)
        resolved_dtype = _normalize_dtype(dtype) if dtype is not None else _infer_dtype([value])
        fill = _coerce_scalar(value, resolved_dtype)
        return Tensor([fill] * _shape_size(s), s, resolved_dtype)

    def random(self, shape: Sequence[Any], dtype: Optional[str] = None) -> Tensor:
        """Uniform random floats in [0, 1)."""
        s = _validate_shape(shape)
        resolved_dtype = _normalize_dtype(dtype) if dtype is not None else 'float64'
        flat = [_coerce_scalar(_random.random(), resolved_dtype) for _ in range(_shape_size(s))]
        return Tensor(flat, s, resolved_dtype)

    def random_normal(self, shape: Sequence[Any], mean: float = 0.0, std: float = 1.0,
                       dtype: Optional[str] = None) -> Tensor:
        if isinstance(std, bool) or not isinstance(std, (int, float)) or std < 0:
            raise BlazeValueError(f"RandomNormal std must be a non-negative number, got {std!r}")
        s = _validate_shape(shape)
        resolved_dtype = _normalize_dtype(dtype) if dtype is not None else 'float64'
        flat = [_coerce_scalar(_random.gauss(mean, std), resolved_dtype) for _ in range(_shape_size(s))]
        return Tensor(flat, s, resolved_dtype)

    def random_uniform(self, shape: Sequence[Any], min: float = 0.0, max: float = 1.0,
                        dtype: Optional[str] = None) -> Tensor:
        if isinstance(min, bool) or isinstance(max, bool) or not isinstance(min, (int, float)) or not isinstance(max, (int, float)):
            raise BlazeTypeError("RandomUniform bounds must be numbers")
        if min > max:
            raise BlazeValueError(f"RandomUniform min ({min}) must not exceed max ({max})")
        s = _validate_shape(shape)
        resolved_dtype = _normalize_dtype(dtype) if dtype is not None else 'float64'
        flat = [_coerce_scalar(_random.uniform(min, max), resolved_dtype) for _ in range(_shape_size(s))]
        return Tensor(flat, s, resolved_dtype)

    def arange(self, start: Any, stop: Any = None, step: Any = 1, dtype: Optional[str] = None) -> Tensor:
        # Arange(stop) form, mirroring the common single-argument shorthand.
        if stop is None:
            start, stop = 0, start
        for name, val in (('start', start), ('stop', stop), ('step', step)):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise BlazeTypeError(f"Arange {name} must be a number, got {type(val).__name__}")
        if step == 0:
            raise BlazeValueError("Arange step must not be zero")

        values = []
        v = start
        if step > 0:
            while v < stop:
                values.append(v)
                v += step
        else:
            while v > stop:
                values.append(v)
                v += step

        resolved_dtype = _normalize_dtype(dtype) if dtype is not None else _infer_dtype(values)
        if not values:
            return Tensor([], (0,), resolved_dtype)
        return Tensor._from_flat(values, (len(values),), resolved_dtype)

    def linspace(self, start: Any, stop: Any, num: int = 50, dtype: Optional[str] = None) -> Tensor:
        """`num` evenly spaced values from `start` to `stop`, both endpoints
        inclusive (matching NumPy's `linspace` default `endpoint=True`)."""
        for name, val in (('start', start), ('stop', stop)):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise BlazeTypeError(f"Linspace {name} must be a number, got {type(val).__name__}")
        if isinstance(num, bool) or not isinstance(num, int):
            raise BlazeTypeError(f"Linspace num must be an integer, got {type(num).__name__}")
        if num < 0:
            raise BlazeValueError(f"Linspace num must be non-negative, got {num}")

        resolved_dtype = _normalize_dtype(dtype) if dtype is not None else 'float64'

        if num == 0:
            return Tensor([], (0,), resolved_dtype)
        if num == 1:
            return Tensor._from_flat([float(start)], (1,), resolved_dtype)

        step = (stop - start) / (num - 1)
        values = [start + step * i for i in range(num - 1)] + [float(stop)]
        return Tensor._from_flat(values, (num,), resolved_dtype)

    def identity(self, size: Any, dtype: Optional[str] = None) -> Tensor:
        if isinstance(size, bool) or not isinstance(size, int):
            raise BlazeTypeError(f"Identity size must be an integer, got {type(size).__name__}")
        if size < 0:
            raise BlazeValueError(f"Identity size must be non-negative, got {size}")
        resolved_dtype = _normalize_dtype(dtype)
        one = 1 if _is_int_dtype(resolved_dtype) else 1.0
        zero = 0 if _is_int_dtype(resolved_dtype) else 0.0
        flat = [one if i == j else zero for i in range(size) for j in range(size)]
        return Tensor(flat, (size, size), resolved_dtype)


def create_tensor_module() -> dict:
    """Create the Tensor module API as a dict of bound methods, matching
    the export shape of create_json_module()/create_math_module().

    Note: the Tensor *class* itself is deliberately not exported under a
    'Tensor' key here. Doing so let `Import tensor` (the bare, no-namespace
    form) dump the raw Python class as a top-level name -- and then
    `Tensor.Create` resolved as an attribute lookup on the *class object*
    itself (an empty PropertyError target type), not a call into this
    module. `Tensor.Create(...)`-style namespaced access is achieved with
    `Import tensor as Tensor`, which binds this whole dict under the name
    `Tensor` -- `Create`, `Zeros`, etc. are looked up as dict keys, never
    through the Python class.
    """
    library = TensorLibrary()
    return {
        "Create": library.create,
        "Zeros": library.zeros,
        "Ones": library.ones,
        "Full": library.full,
        "Random": library.random,
        "RandomNormal": library.random_normal,
        "RandomUniform": library.random_uniform,
        "Arange": library.arange,
        "Linspace": library.linspace,
        "Identity": library.identity,
    }