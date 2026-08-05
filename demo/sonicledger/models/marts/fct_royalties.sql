select
    stream_id,
    artist_id,
    track_id,
    territory_code,
    stream_count,
    rate_per_stream,
    royalty_amount
from {{ ref('stg_streams') }}
