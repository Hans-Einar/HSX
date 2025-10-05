; ModuleID = 'C:\Users\hanse\git\HSX\examples\c\icmp.c'
source_filename = "C:\\Users\\hanse\\git\\HSX\\examples\\c\\icmp.c"
target datalayout = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-windows-msvc19.43.34810"

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  store i32 0, ptr %1, align 4
  store i32 5, ptr %2, align 4
  store i32 3, ptr %3, align 4
  %7 = load i32, ptr %2, align 4
  %8 = load i32, ptr %3, align 4
  %9 = icmp eq i32 %7, %8
  %10 = zext i1 %9 to i32
  store i32 %10, ptr %4, align 4
  %11 = load i32, ptr %2, align 4
  %12 = load i32, ptr %3, align 4
  %13 = icmp sgt i32 %11, %12
  %14 = zext i1 %13 to i32
  store i32 %14, ptr %5, align 4
  %15 = load i32, ptr %2, align 4
  %16 = load i32, ptr %3, align 4
  %17 = icmp slt i32 %15, %16
  %18 = zext i1 %17 to i32
  store i32 %18, ptr %6, align 4
  %19 = load i32, ptr %4, align 4
  %20 = load i32, ptr %5, align 4
  %21 = load i32, ptr %5, align 4
  %22 = add nsw i32 %20, %21
  %23 = add nsw i32 %19, %22
  %24 = load i32, ptr %6, align 4
  %25 = load i32, ptr %6, align 4
  %26 = add nsw i32 %24, %25
  %27 = load i32, ptr %6, align 4
  %28 = add nsw i32 %26, %27
  %29 = load i32, ptr %6, align 4
  %30 = add nsw i32 %28, %29
  %31 = add nsw i32 %23, %30
  ret i32 %31
}

attributes #0 = { noinline nounwind optnone uwtable "min-legal-vector-width"="0" "no-builtins" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.module.flags = !{!0, !1, !2, !3}
!llvm.ident = !{!4}

!0 = !{i32 1, !"wchar_size", i32 2}
!1 = !{i32 8, !"PIC Level", i32 2}
!2 = !{i32 7, !"uwtable", i32 2}
!3 = !{i32 1, !"MaxTLSAlign", i32 65536}
!4 = !{!"clang version 18.1.8"}
