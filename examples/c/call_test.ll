declare i32 @callee(i32, i32)

define dso_local i32 @caller(i32 %x) {
entry:
  %r = call i32 @callee(i32 %x, i32 5)
  ret i32 %r
}
