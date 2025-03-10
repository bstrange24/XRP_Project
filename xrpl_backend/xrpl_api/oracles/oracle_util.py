import logging

from django.http import JsonResponse
from xrpl.models import AccountObjects, AccountObjectType, OracleDelete
import datetime

from xrpl.models.transactions.oracle_set import PriceData, OracleSet
from xrpl.utils import str_to_hex

logger = logging.getLogger('xrpl_app')

def process_oracle_price_data_results(get_oracle_price_data_result):
    # define array for holding oracles an account has created
    oracles = []

    # parse the result and print
    if "account_objects" in get_oracle_price_data_result and len(get_oracle_price_data_result["account_objects"]) > 0:
        oracles = get_oracle_price_data_result["account_objects"]
        for oracle in oracles:
            oracle_data = {}
            price_data_ = []
            oracle_data["oracle_id"] = oracle["index"]
            oracle_data["owner"] = oracle["Owner"]
            oracle_data["provider"] = oracle["Provider"]
            oracle_data["asset_class"] = oracle["AssetClass"]
            oracle_data["uri"] = oracle["URI"] if "URI" in oracle else ""
            oracle_data["last_update_time"] = (
                str(datetime.datetime.fromtimestamp(oracle["LastUpdateTime"]))
                if "LastUpdateTime" in oracle
                else ""
            )
            oracle_data["price_data_series"] = (
                oracle["PriceDataSeries"] if "PriceDataSeries" in oracle else []
            )

            # sort price data series if any
            if "PriceDataSeries" in oracle and len(oracle["PriceDataSeries"]) > 0:
                price_data_series = oracle["PriceDataSeries"]
                for price_data_serie in price_data_series:
                    price_data = {}
                    price_data["base_asset"] = price_data_serie["PriceData"]["BaseAsset"]

                    price_data["quote_asset"] = price_data_serie["PriceData"]["QuoteAsset"]

                    price_data["scale"] = (
                        price_data_serie["PriceData"]["Scale"]
                        if "Scale" in price_data_serie["PriceData"]
                        else ""
                    )
                    price_data["asset_price"] = (
                        price_data_serie["PriceData"]["AssetPrice"]
                        if "AssetPrice" in price_data_serie["PriceData"]
                        else ""
                    )

                    price_data_.append(price_data)
                oracle_data["price_data_series"] = price_data_
            oracles.append(oracle_data)
            logger.info(f"Price oracles: {oracles}")
            return True
    else:
        return False


def prepare_create_oracle_data(base_asset, quote_asset, price, scale_value):
    return PriceData(
        base_asset=base_asset,
        quote_asset=quote_asset,
        asset_price=int(price),
        scale=int(scale_value),
    )

def prepare_create_oracle_set_data(address, oracle_document_id, provider, uri, last_update_time, asset_class, price_data_array):
    return OracleSet(
            account=address,
            oracle_document_id=int(oracle_document_id),
            provider=str_to_hex(provider),
            uri=str_to_hex(uri),
            last_update_time=last_update_time,
            asset_class=str_to_hex(asset_class),
            price_data_series=price_data_array,
        )

def prepare_get_oracle_data(oracle_creator):
    return AccountObjects(
        account=oracle_creator,
        ledger_index="validated",
        type=AccountObjectType.ORACLE,
    )

def prepare_get_oracle_data_with_pagination(oracle_creator, marker):
    return AccountObjects(
        account=oracle_creator,
        ledger_index="validated",
        type=AccountObjectType.ORACLE,
        limit=100,
        marker=marker,
    )

def prepare_oracle_delete_data(address, document_id):
    return OracleDelete(
        account=address,
        oracle_document_id=document_id,
    )

def get_oracle_data_response(response, oracle_created):
    if oracle_created:
        return JsonResponse({
            "status": "success",
            "message": "Price Oracle retrieved successfully.",
            "result": response,
        })
    else:
        return JsonResponse({
            "status": "success",
            "message": "No Price Oracles found for this account.",
        })

def create_oracle_data(response):
    return JsonResponse({
        "status": "success",
        "message": "Created Price Oracle successfully.",
        "result": response,
    })

def create_oracle_delete_data(response):
    return JsonResponse({
        "status": "success",
        "message": "Deleted Price Oracle successfully.",
        "result": response,
    })

def oracles_with_pagination_response(paginated_transactions, paginator):
    return JsonResponse({
        "status": "success",
        "message": "Price Oracles successfully retrieved.",
        "oracles": list(paginated_transactions),
        "oracle_count": paginator.count,
        "pages": paginator.num_pages,
        "current_page": paginated_transactions.number,
    })

