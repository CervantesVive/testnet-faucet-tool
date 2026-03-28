import yaml
from pathlib import Path
from handlers.base import BaseHandler

_REGISTRY: dict[str, dict] | None = None
_HANDLER_CACHE: dict[str, BaseHandler] = {}

FAMILY_HANDLER_MAP: dict[str, str] = {
    "evm": "handlers.evm.EvmHandler",
    "solana": "handlers.solana.SolanaHandler",
    "cosmos": "handlers.cosmos.CosmosHandler",
    "sui": "handlers.sui.SuiHandler",
    "aptos": "handlers.aptos.AptosHandler",
    "near": "handlers.near.NearHandler",
    "xrp": "handlers.xrp.XrpHandler",
    "stellar": "handlers.stellar.StellarHandler",
    "tron": "handlers.tron.TronHandler",
    "ton": "handlers.ton.TonHandler",
    "hedera": "handlers.hedera.HederaHandler",
    "utxo": "handlers.utxo.UtxoHandler",
    "algorand": "handlers.algorand.AlgorandHandler",
    "cardano": "handlers.cardano.CardanoHandler",
    "eos": "handlers.eos.EosHandler",
    "substrate": "handlers.substrate.SubstrateHandler",
    "stacks": "handlers.stacks.StacksHandler",
    "flow": "handlers.flow.FlowHandler",
    "vechain": "handlers.vechain.VeChainHandler",
    "tezos": "handlers.tezos.TezosHandler",
    "zcash": "handlers.zcash.ZcashHandler",
    "icp": "handlers.icp.IcpHandler",
    "bittensor": "handlers.bittensor.BittensorHandler",
    "avalanche_p": "handlers.avalanche.AvalanchePHandler",
    "canton": "handlers.canton.CantonHandler",
}


def _get_chains_yaml_path() -> Path:
    return Path(__file__).parent.parent / "config" / "chains.yaml"


def load_registry() -> dict[str, dict]:
    global _REGISTRY
    if _REGISTRY is None:
        path = _get_chains_yaml_path()
        if not path.exists():
            raise FileNotFoundError(f"chains.yaml not found at {path}")
        with open(path) as f:
            _REGISTRY = yaml.safe_load(f) or {}
    return _REGISTRY


def get_asset_config(asset_id: str) -> dict:
    registry = load_registry()
    if asset_id not in registry:
        raise KeyError(f"Unknown asset: {asset_id}")
    return registry[asset_id]


def get_all_assets() -> dict[str, dict]:
    return load_registry()


def get_handler(asset_id: str) -> BaseHandler:
    if asset_id in _HANDLER_CACHE:
        return _HANDLER_CACHE[asset_id]

    config = get_asset_config(asset_id)
    family = config.get("family")
    if not family:
        raise ValueError(f"Asset {asset_id} has no 'family' field in registry")

    handler_path = FAMILY_HANDLER_MAP.get(family)
    if not handler_path:
        raise NotImplementedError(f"No handler registered for family: {family}")

    module_path, class_name = handler_path.rsplit(".", 1)
    try:
        import importlib
        module = importlib.import_module(module_path)
        handler_class = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise NotImplementedError(f"Handler not yet implemented for family '{family}': {e}")

    handler = handler_class(config)
    _HANDLER_CACHE[asset_id] = handler
    return handler
