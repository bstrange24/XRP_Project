import json
import logging

from ..models.ledger_models import Ledger, ValidatedLedger, StateAccountingEntry, Port, LastClose, ServerInfo

logger = logging.getLogger('xrpl_app')


def save_ledger_info(json_data):
    # Parse JSON
    data = json.loads(json_data) if isinstance(json_data, str) else json_data
    ledger_data = data["ledger"]

    # Create or update Ledger instance
    ledger, created = Ledger.objects.update_or_create(
        ledger_index=ledger_data["ledger_index"],
        defaults={
            "account_hash": ledger_data["account_hash"],
            "close_flags": ledger_data["close_flags"],
            "close_time": ledger_data["close_time"],
            "close_time_human": ledger_data["close_time_human"],
            "close_time_iso": ledger_data["close_time_iso"],
            "close_time_resolution": ledger_data["close_time_resolution"],
            "closed": ledger_data["closed"],
            "ledger_hash": ledger_data["ledger_hash"],
            "parent_close_time": ledger_data["parent_close_time"],
            "parent_hash": ledger_data["parent_hash"],
            "total_coins": ledger_data["total_coins"],
            "transaction_hash": ledger_data["transaction_hash"],
            "validated": data["validated"]
        }
    )
    print(Ledger.objects.first().created_at)
    return ledger

def save_server_info(json_data):
    # Parse JSON
    data = json.loads(json_data) if isinstance(json_data, str) else json_data
    info = data["info"]

    # Create ServerInfo instance
    server_info = ServerInfo(
        build_version=info["build_version"],
        complete_ledgers=info["complete_ledgers"],
        hostid=info["hostid"],
        initial_sync_duration_us=info["initial_sync_duration_us"],
        io_latency_ms=info["io_latency_ms"],
        jq_trans_overflow=info["jq_trans_overflow"],
        load_factor=info["load_factor"],
        network_id=info["network_id"],
        peer_disconnects=info["peer_disconnects"],
        peer_disconnects_resources=info["peer_disconnects_resources"],
        peers=info["peers"],
        pubkey_node=info["pubkey_node"],
        server_state=info["server_state"],
        server_state_duration_us=info["server_state_duration_us"],
        time=info["time"],
        uptime=info["uptime"],
        validation_quorum=info["validation_quorum"]
    )
    server_info.save()

    # LastClose
    LastClose.objects.create(
        server_info=server_info,
        converge_time_s=info["last_close"]["converge_time_s"],
        proposers=info["last_close"]["proposers"]
    )

    # Ports
    for port_data in info["ports"]:
        Port.objects.create(
            server_info=server_info,
            port=port_data["port"],
            protocol=port_data["protocol"]
        )

    # StateAccounting
    for state, details in info["state_accounting"].items():
        StateAccountingEntry.objects.create(
            server_info=server_info,
            state=state,
            duration_us=details["duration_us"],
            transitions=details["transitions"]
        )

    # ValidatedLedger
    ValidatedLedger.objects.create(
        server_info=server_info,
        age=info["validated_ledger"]["age"],
        base_fee_xrp=info["validated_ledger"]["base_fee_xrp"],
        hash=info["validated_ledger"]["hash"],
        reserve_base_xrp=info["validated_ledger"]["reserve_base_xrp"],
        reserve_inc_xrp=info["validated_ledger"]["reserve_inc_xrp"],
        seq=info["validated_ledger"]["seq"]
    )

    return server_info