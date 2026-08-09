from collections.abc import Mapping
from dataclasses import dataclass

from .models import MetadataEvidence, RegionExposure, RegionRisk, SqlDependency

REGION_ORDER = ("NORTHEAST", "SOUTH", "MIDWEST", "WEST", "UNKNOWN")


@dataclass(frozen=True)
class AssetRegionMetadata:
    regions: tuple[str, ...]
    owners: tuple[str, ...]
    policy_flags: tuple[str, ...] = ()
    critical_customer_data: bool = False


ASTERVALE_ASSET_REGIONS: Mapping[str, AssetRegionMetadata] = {
    "fct_order_sales": AssetRegionMetadata(
        regions=("NORTHEAST", "SOUTH", "MIDWEST", "WEST"),
        owners=("commerce-analytics@astervale.demo",),
    ),
    "loyalty_customer_value": AssetRegionMetadata(
        regions=("NORTHEAST", "WEST"),
        owners=("loyalty-platform@astervale.demo",),
        policy_flags=("CUSTOMER_DATA", "CA_PRIVACY_REVIEW"),
        critical_customer_data=True,
    ),
    "regional_returns": AssetRegionMetadata(
        regions=("SOUTH", "MIDWEST", "WEST"),
        owners=("store-operations@astervale.demo",),
    ),
    "executive_revenue_dashboard": AssetRegionMetadata(
        regions=("NORTHEAST", "SOUTH", "MIDWEST", "WEST"),
        owners=("finance-data@astervale.demo",),
        policy_flags=("EXECUTIVE_REPORTING",),
    ),
}


def assess_regions(
    evidence: MetadataEvidence,
    sql_dependencies: tuple[SqlDependency, ...],
    asset_regions: Mapping[str, AssetRegionMetadata],
) -> tuple[RegionExposure, ...]:
    assets_by_name = {asset.name: asset for asset in evidence.downstream}
    exposures: list[RegionExposure] = []

    for region in REGION_ORDER:
        names: list[str] = []
        owners: list[str] = []
        flags: list[str] = []
        critical_customer_data = False

        for asset_name, metadata in asset_regions.items():
            if asset_name not in assets_by_name or region not in metadata.regions:
                continue
            names.append(asset_name)
            owners.extend(metadata.owners)
            flags.extend(metadata.policy_flags)
            critical_customer_data = (
                critical_customer_data or metadata.critical_customer_data
            )

        sql_objects = [
            dependency.object_name
            for dependency in sql_dependencies
            if region in dependency.regions or (region == "UNKNOWN" and not dependency.regions)
        ]

        if region == "UNKNOWN":
            flags.append("REGION_METADATA_MISSING")
            risk = RegionRisk.REVIEW
        elif critical_customer_data:
            risk = RegionRisk.HIGH
        else:
            risk = RegionRisk.MEDIUM

        exposures.append(
            RegionExposure(
                region=region,
                asset_names=_unique(names),
                sql_objects=_unique(sql_objects),
                owners=_unique(owners),
                policy_flags=_unique(flags),
                risk=risk,
            )
        )

    return tuple(exposures)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
