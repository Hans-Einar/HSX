; ModuleID = 'C:\Users\hanse\git\HSX\examples\c\half.c'
source_filename = "C:\\Users\\hanse\\git\\HSX\\examples\\c\\half.c"
target datalayout = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-windows-msvc19.43.34810"

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @half_ops(half noundef %0, half noundef %1) #0 {
  %3 = alloca half, align 2
  %4 = alloca half, align 2
  %5 = alloca half, align 2
  %6 = alloca half, align 2
  %7 = alloca half, align 2
  store half %1, ptr %3, align 2
  store half %0, ptr %4, align 2
  %8 = load half, ptr %4, align 2
  %9 = fpext half %8 to float
  %10 = load half, ptr %3, align 2
  %11 = fpext half %10 to float
  %12 = fadd float %9, %11
  %13 = fptrunc float %12 to half
  store half %13, ptr %5, align 2
  %14 = load half, ptr %4, align 2
  %15 = fpext half %14 to float
  %16 = load half, ptr %3, align 2
  %17 = fpext half %16 to float
  %18 = fmul float %15, %17
  %19 = fptrunc float %18 to half
  store half %19, ptr %6, align 2
  %20 = load half, ptr %5, align 2
  %21 = fpext half %20 to float
  %22 = load half, ptr %6, align 2
  %23 = fpext half %22 to float
  %24 = fadd float %21, %23
  %25 = fptrunc float %24 to half
  store half %25, ptr %7, align 2
  %26 = load half, ptr %7, align 2
  %27 = fptosi half %26 to i32
  %28 = call i32 @use_val(i32 noundef %27) #1
  ret i32 %28
}

; Function Attrs: noinline nounwind optnone uwtable
define internal i32 @use_val(i32 noundef %0) #0 {
  %2 = alloca i32, align 4
  store i32 %0, ptr %2, align 4
  %3 = load i32, ptr %2, align 4
  %4 = add nsw i32 %3, 1
  ret i32 %4
}

attributes #0 = { noinline nounwind optnone uwtable "min-legal-vector-width"="0" "no-builtins" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nobuiltin "no-builtins" }

!llvm.module.flags = !{!0, !1, !2, !3}
!llvm.ident = !{!4}

!0 = !{i32 1, !"wchar_size", i32 2}
!1 = !{i32 8, !"PIC Level", i32 2}
!2 = !{i32 7, !"uwtable", i32 2}
!3 = !{i32 1, !"MaxTLSAlign", i32 65536}
!4 = !{!"clang version 18.1.8"}
