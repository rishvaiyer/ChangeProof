select
    artist_id,
    sum(stream_count) as total_streams,
    cast(sum(royalty_amount) as decimal(12, 4)) as total_royalty_amount
from {{ ref('fct_royalties') }}
group by 1
