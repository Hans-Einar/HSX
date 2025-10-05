define dso_local i32 @cmp_slt(i32 %a, i32 %b) {
entry:
  %lt = icmp slt i32 %a, %b
  ret i32 %lt
}

