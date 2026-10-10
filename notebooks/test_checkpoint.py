from src.utils.checkpoint import CheckpointManager


checkpoint_manager = CheckpointManager()


print("=== CHECKPOINT TEST ===")


checkpoint = checkpoint_manager.load(
    entity="commits"
)

print(f"Current checkpoint: {checkpoint}")


checkpoint_manager.save(
    entity="commits",
    last_processed_at="2026-10-05T14:20:00Z"
)


checkpoint = checkpoint_manager.load(
    entity="commits"
)

print(f"Updated checkpoint: {checkpoint}")