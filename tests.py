from .flickrmirrorer import get_photo_datetime


def test_unparseable_title_timestamp():
    timestamp = get_photo_datetime({
        'datetakenunknown': '1',
        'datetaken': '2014-10-01 13:45:37',
        'title': 'flaskpost'
    })

    # Fall back on datetaken if we can't parse the date from the title
    assert timestamp.isoformat() == "2014-10-01T13:45:37"


def test_plain_title_timestamp():
    timestamp = get_photo_datetime({
        'datetakenunknown': '1',
        'datetaken': '2014-10-01 13:45:37',
        'title': '20151130_135610'
    })
    assert timestamp.isoformat() == "2015-11-30T13:56:10"


def test_known_timestamp():
    timestamp = get_photo_datetime({
        'datetakenunknown': '0',
        'datetaken': '2015-11-02 12:35:07'
    })
    assert timestamp.isoformat() == "2015-11-02T12:35:07"
