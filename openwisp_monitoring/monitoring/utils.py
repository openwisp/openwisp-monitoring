from django.utils.text import slugify


def clean_timeseries_data_key(value):
    value = value.replace('.', '_')
    return slugify(value).replace('-', '_')
