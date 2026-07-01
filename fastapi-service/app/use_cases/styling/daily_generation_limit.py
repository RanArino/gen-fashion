from datetime import datetime, timezone

from app.config import Settings
from app.domain.styling.exceptions import DailyGenerationLimitExceeded
from app.ports import StylingRepositoryPort


async def enforce_daily_generation_limit(
    styling_repo: StylingRepositoryPort,
    settings: Settings,
    user_id: str,
) -> None:
    if settings.max_daily_generations_per_user <= 0:
        return

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    count = await styling_repo.count_completed_today(user_id, today_start)
    if count >= settings.max_daily_generations_per_user:
        raise DailyGenerationLimitExceeded(
            f"Daily generation limit of "
            f"{settings.max_daily_generations_per_user} reached. "
            f"Limit resets at midnight UTC."
        )
