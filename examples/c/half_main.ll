; ModuleID = 'C:\Users\hanse\git\HSX\examples\tests\half_main_opt.bc'
source_filename = "llvm-link"
target datalayout = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-windows-msvc19.43.34810"

; Function Attrs: noinline nounwind uwtable
define dso_local i32 @main() #0 {
  %1 = call i32 @half_ops(half noundef 0xH3E00, half noundef 0xH4080) #1
  ret i32 %1
}

; Function Attrs: noinline nounwind uwtable
define dso_local i32 @half_ops(half noundef %0, half noundef %1) #0 {
  %3 = fadd half %0, %1
  %4 = fmul half %0, %1
  %5 = fadd half %3, %4
  %6 = fptosi half %5 to i32
  %7 = call i32 @use_val(i32 noundef %6) #1
  ret i32 %7
}

; Function Attrs: noinline nounwind uwtable
define internal i32 @use_val(i32 noundef %0) #0 {
  %2 = add nsw i32 %0, 1
  ret i32 %2
}

attributes #0 = { noinline nounwind uwtable "min-legal-vector-width"="0" "no-builtins" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nobuiltin "no-builtins" }

!llvm.ident = !{!0, !0}
!llvm.module.flags = !{!1, !2, !3, !4}

!0 = !{!"clang version 18.1.8"}
!1 = !{i32 1, !"wchar_size", i32 2}
!2 = !{i32 8, !"PIC Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 2}
!4 = !{i32 1, !"MaxTLSAlign", i32 65536}
