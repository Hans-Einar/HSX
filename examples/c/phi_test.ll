define dso_local i32 @phi_example(i1 %cond, i32 %a, i32 %b) {
entry:
  br i1 %cond, label %then, label %else
then:
  br label %merge
else:
  br label %merge
merge:
  %phi = phi i32 [ %a, %then ], [ %b, %else ]
  ret i32 %phi
}
