# By default age is calculated from the date the index is created but if the
# index has been rolled over than the rollover date is used to calculate the age

default_rp_policy = {
    'policy': {
        'phases': {
            'hot': {
                'actions': {
                    'rollover': {'max_age': '30d', 'max_size': '90G'},
                    'set_priority': {'priority': 100},
                }
            },
            'warm': {
                'min_age': '30d',
                'actions': {
                    'forcemerge': {'max_num_segments': 1},
                    'allocate': {'number_of_replicas': 0},
                    'set_priority': {'priority': 50},
                },
            },
            'cold': {'min_age': '150d', 'actions': {'freeze': {}}},
            'delete': {'min_age': '335d', 'actions': {'delete': {}}},
        }
    }
}


def _make_policy(max_age):
    return {
        'policy': {
            'phases': {
                'hot': {
                    'actions': {
                        'rollover': {'max_age': max_age},
                        'set_priority': {'priority': 100},
                    }
                },
                'delete': {'actions': {'delete': {}}},
            }
        }
    }
