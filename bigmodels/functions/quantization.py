from ..allocator import Allocator
import cupy
from ..backend import create_reduction_func, create_ufunc

_min_max_preamble = '''
template <typename T>
struct min_max_st{
    T value;
    int index;
    __device__ min_max_st() : index(-1) { }
    __device__ min_max_st(T v) : value(v), index(0) { }
    __device__ min_max_st(T v, int i) : value(v), index(i) { }
};
template <typename T>
__device__ min_max_st<T> my_max(
        const min_max_st<T>& a, const min_max_st<T>& b) {
    if (a.index == -1) return b;
    if (b.index == -1) return a;
    return min_max_st<T>(max(abs(a.value), abs(b.value)));
}
'''

quantize_scale_kernel = create_reduction_func(
    'bms_quantize_scale',
    ('e->e', 'f->f'),
    ('min_max_st<type_in0_raw>(in0)', 'my_max(a, b)', 'out0 = abs(a.value) / 120',
     'min_max_st<type_in0_raw>'), None, _min_max_preamble)

quantize_copy = create_ufunc('bms_quantize_copy', ('ef->b', 'ff->b'), 'out0 = round(in0 / in1)')

def quantize(x : cupy.ndarray, out : cupy.ndarray):
    if not cupy.issubdtype(x.dtype, cupy.floating):
        raise RuntimeError("Quantize tensor dtype is %s" % x.dtype)
    assert x.shape == out.shape
    
    scale = quantize_scale_kernel(x) # scale on gpu
    quantize_copy(x, scale, out=out)
    return scale