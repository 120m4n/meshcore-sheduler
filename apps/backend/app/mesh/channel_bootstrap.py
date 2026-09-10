import logging

from meshcore import EventType, MeshCore

logger = logging.getLogger("mesh.channel_bootstrap")

MAX_CHANNEL_SLOTS = 8


def _channel_name(payload: dict) -> str:
    name = payload.get("channel_name", "")
    if isinstance(name, (bytes, bytearray)):
        name = name.decode("utf-8", errors="ignore")
    return name.rstrip("\x00")


async def ensure_channel(mc: MeshCore, name: str, idx: int) -> None:
    """Scan every slot for `name` before provisioning at `idx`. Gap register
    §8.1: checking only `idx` would silently create a duplicate channel if
    `name` already exists elsewhere on the companion."""
    for slot in range(MAX_CHANNEL_SLOTS):
        res = await mc.commands.get_channel(slot)
        if res.is_error():
            continue
        if _channel_name(res.payload) == name:
            if slot == idx:
                logger.info("channel %s confirmed at idx %d", name, idx)
            else:
                logger.warning(
                    "channel %s found at idx %d, not configured idx %d — "
                    "using the existing slot's contents, not reprovisioning",
                    name,
                    slot,
                    idx,
                )
            return

    logger.warning("channel %s not found in any slot — provisioning at idx %d", name, idx)
    res = await mc.commands.set_channel(idx, name)
    if res.is_error():
        raise RuntimeError(f"failed to provision channel {name!r} at idx {idx}: {res.payload}")
    logger.info("channel %s provisioned at idx %d", name, idx)
