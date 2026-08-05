select
    cast(stream_id as integer) as stream_id,
    cast(artist_id as varchar) as artist_id,
    cast(track_id as varchar) as track_id,
    cast(territory_code as varchar) as territory_code,
    cast(stream_count as integer) as stream_count,
    cast(rate_per_stream as decimal(10, 4)) as rate_per_stream,
    cast(stream_count * rate_per_stream as decimal(12, 4)) as royalty_amount
from {{ ref('raw_dsp_streams') }}
