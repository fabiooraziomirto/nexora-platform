;; Minimal WASI module: writes a fixed JSON line to stdout (fd 1).
;; Proves the runtime executes real WASM and captures stdout.
(module
  (import "wasi_snapshot_preview1" "fd_write"
    (func $fd_write (param i32 i32 i32 i32) (result i32)))
  (memory 1)
  (export "memory" (memory 0))
  ;; JSON payload at offset 8 (24 bytes incl trailing newline)
  (data (i32.const 8) "{\"status\":\"ok\"}\0a")
  (func $main (export "_start")
    (i32.store (i32.const 0) (i32.const 8))    ;; iov.iov_base = 8
    (i32.store (i32.const 4) (i32.const 16))   ;; iov.iov_len  = 16
    (call $fd_write
      (i32.const 1)    ;; fd = stdout
      (i32.const 0)    ;; iovs ptr
      (i32.const 1)    ;; iovs count
      (i32.const 24))  ;; nwritten out ptr
    drop))
