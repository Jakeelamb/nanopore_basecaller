# Source runtime diagnostics

The unchanged source executable successfully basecalled the 32-parent HG002 development smoke set in ordinary execution and under separate CUDA/NVTX tracing. Native quickcheck, full SAM decode, and the frozen BAM parser accept all three diagnostic outputs with all 32 original parents represented. These diagnostics are separate from controlled qualification and supply no benchmark timing or speedup claim.

The [diagnostic manifest](../provenance/verification/source-profile-20261023.json) pins the build, native outputs, traces, logs, projection source, and verifier. The successful producer receipt is `logs/20261023T024057Z-source-profile-isolation-lqasiw`. An initial projection used a nonexistent metric key; its failure is retained. Correcting the projection reused the same successful native outputs without another GPU run.

## Observed CUDA paths

Nsight Systems CLI 2026.5.1.161 collected CUDA and NVTX traces without CPU sampling or context-switch collection. The official NVIDIA package SHA-256 is `61829db6392e5c293ada1319df86a97c3356bc810335a1975cb551fcfe3eca08`. It was extracted into a local ignored prefix. Its [CLI documentation](https://docs.nvidia.com/nsight-systems/UserGuide/index.html) describes these tracing and NVTX facilities.

The HAC diagnostic includes `flstm_layer`, `nn_forward`, `gpu_decode`, `cpu_decode`, and chunk-processing NVTX ranges. Kernel symbols include `flstm`, `flstm_dn_h_up_xh`, `factorised_linear`, convolution kernels, and the four Koi decoding steps. The FLSTM symbol templates name an FP8 representation. That establishes observed optimized kernel families, not their complete numerical semantics.

The SUP diagnostic logs `TxEncoderStack: use_koi_tiled true` and contains `TxLayerKoiTiled` ranges. Matmul and SwiGLU kernel templates name `__nv_fp8_e4m3`; tiled residual/RMS normalization and decoder kernels also appear. This is runtime evidence for the hardware-dependent tiled/FP8 branch described in [the source trace](dorado-code-path.md). It does not reveal opaque Koi kernel bodies or establish equivalence with fallback arithmetic.

Automatic batch selection ran inside these diagnostic processes. HAC used chunk sizes 12288 and 6144; SUP used 12288. The raw stderr preserves the chosen batch capacities. Startup benchmarking contributes many model forwards, so whole-process kernel percentages do not describe steady-state basecalling. Nested NVTX durations overlap, and host range duration is not GPU execution duration. No memory bandwidth, occupancy, compute-limit, or full-workload bottleneck conclusion is drawn here.

## Preserved tracing failure

The initial `--trace=cuda,nvtx,osrt` collection ended with exit 139 before emitting a BAM. Dorado PID 888823 received SIGSEGV; the crash reporter retained a core. The faulting thread repeatedly cycles through Nsight's `NSYS_OSRT_pthread_mutex_trylock_1`, Dorado allocator functions, `pthread_setspecific`, and Nsight injection allocation. Another thread was reading POD5 metadata through Arrow. Approximately 70 GiB RAM remained available and the inspected kernel journal contained no OOM entry.

The failed run is `logs/20261023T023819Z-source-profile-hac-retry-eh5jur`. `logs/20261023T023956Z-source-profile-crash-info-yB8rhz` retains `coredumpctl info 888823`. Its trace contains no CUDA or NVTX data and is not a successful profile. Ordinary HAC execution and both CUDA/NVTX-only collections passed afterward with the same executable, models, signals, and read IDs. Together these observations implicate OS-runtime tracing's allocator/mutex interception. They do not prove the exact profiler defect or qualify OS-runtime tracing on this host. No source, binary, library, system setting, or raw input was changed to obtain the successful runs.

Other retained attempts include a local-package extraction failure caused by assuming the wrong archive member, and two native launch attempts rejected before execution by the shared host lock. The archive was re-extracted from its already verified bytes. Native execution respected the lock used by another checkout.

## Reproduce the accepted collection

The exact standalone command script is retained and hashed in the manifest at `logs/source-qualification-20261023/profile-diagnostics.sh`. It acquires `results/stock/host.lock`, checks the source executable hash, runs ordinary HAC smoke, then profiles HAC and SUP sequentially. It writes native BAM, full SAM, stderr, `.nsys-rep`, SQLite, and native `nsys stats` reports under `results/source-profile/20261023`. Existing outputs are not overwritten. Use a new owned directory for another collection.

The successful profiling options were:

```sh
nsys profile --trace=cuda,nvtx --sample=none --cpuctxsw=none --output=OWNED_TRACE \
  bash -c 'exec "$1" basecaller "$2" "$3" --read-ids "$4" --device cuda:0 --batchsize 0 --min-qscore 0 --trim all -v >"$5" 2>"$6"' \
  -- SOURCE_DORADO MODEL HG002_POD5 SMOKE_IDS OWNED_BAM OWNED_STDERR
nsys stats --report cuda_api_sum,cuda_gpu_kern_sum,cuda_gpu_mem_time_sum,nvtx_sum \
  --format csv OWNED_TRACE.nsys-rep
```

The original OS-runtime crash, failed observation, and corrected projection remain part of the evidence. Full development/validation native and accuracy acceptance belongs to the separate source qualification report.
