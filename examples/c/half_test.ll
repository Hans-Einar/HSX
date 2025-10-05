define dso_local i32 @half_ops(half %a, half %b) {
entry:
  %sum = fadd half %a, %b
  %wide = fpext half %sum to float
  %back = fptrunc float %wide to half
  %call = call i32 @use_val(i32 0)
  %res = add i32 %call, 1
  ret i32 %res
}

declare i32 @use_val(i32)
