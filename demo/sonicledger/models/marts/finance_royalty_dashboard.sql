select
    artist_id,
    total_streams,
    total_royalty_amount,
    case
        when total_royalty_amount >= 15 then 'priority'
        when total_royalty_amount >= 8 then 'watch'
        else 'standard'
    end as payout_band
from {{ ref('artist_payouts') }}
