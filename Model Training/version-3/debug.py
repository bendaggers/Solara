from src.checkpoint_db import FastCheckpointManager

mgr = FastCheckpointManager("checkpoints/fast.db")
stats = mgr.get_progress_stats()
print("Stats dictionary keys:", stats.keys())
print("\nFull stats:")
for key, value in stats.items():
    print(f"  {key}: {value}")

# Also check what's in the database
completed = mgr.get_completed_ids()
print(f"\nCompleted configs: {len(completed)}")
if completed:
    print(f"First few: {completed[:5]}")