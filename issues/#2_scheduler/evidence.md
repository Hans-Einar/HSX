# Scheduler Evidence

## Scheduler counters
{2: {'step': 5, 'rotate': 5}, 1: {'rotate': 5, 'step': 5}}

## Scheduler trace (last 5)
{'event': 'rotate', 'ts': 244049.541969525, 'pid': 2}
{'event': 'step', 'ts': 244049.542006044, 'pid': 2, 'pc': 1288}
{'event': 'rotate', 'ts': 244049.542067162, 'pid': 1}
{'event': 'step', 'ts': 244049.542100081, 'pid': 1, 'pc': 1288}
{'event': 'rotate', 'ts': 244049.542159401, 'pid': 2}

## Dumpregs (consumer)
{'pc': 1288, 'sp': 4096, 'reg_base': 4096, 'stack_base': 61440}
R0..R3: [4294967043, 0, 0, 0]

## Mailbox snapshot
{'descriptor_id': 1, 'namespace': 1, 'name': 'stdio.in', 'owner_pid': 1, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 1, 'waiters': [], 'taps': []}
{'descriptor_id': 2, 'namespace': 1, 'name': 'stdio.out', 'owner_pid': 1, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 1, 'waiters': [], 'taps': []}
{'descriptor_id': 3, 'namespace': 1, 'name': 'stdio.err', 'owner_pid': 1, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 1, 'waiters': [], 'taps': []}
{'descriptor_id': 4, 'namespace': 0, 'name': 'pid:1', 'owner_pid': 1, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 0, 'waiters': [], 'taps': []}
{'descriptor_id': 5, 'namespace': 1, 'name': 'stdio.in', 'owner_pid': 2, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 1, 'waiters': [], 'taps': []}
{'descriptor_id': 6, 'namespace': 1, 'name': 'stdio.out', 'owner_pid': 2, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 1, 'waiters': [], 'taps': []}
{'descriptor_id': 7, 'namespace': 1, 'name': 'stdio.err', 'owner_pid': 2, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 1, 'waiters': [], 'taps': []}
{'descriptor_id': 8, 'namespace': 0, 'name': 'pid:2', 'owner_pid': 2, 'capacity': 64, 'bytes_used': 0, 'queue_depth': 0, 'head_seq': 0, 'next_seq': 0, 'mode_mask': 3, 'subscriber_count': 0, 'waiters': [], 'taps': []}
