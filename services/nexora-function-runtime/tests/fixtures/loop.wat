;; Infinite loop — used to verify fuel-based timeout traps execution.
(module
  (func $main (export "_start")
    (loop $l (br $l))))
