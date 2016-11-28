# encoding: utf-8
#
# Copyright (c) 2015 Glencoe Software, Inc. All rights reserved.
#
# This software is distributed under the terms described by the LICENCE file
# you can find at the root of the distribution bundle.
# If the file is missing please request a copy by contacting
# support@glencoesoftware.com.

import logging
import math
import time

from pprint import pformat

from elasticsearch import Elasticsearch
from flask import Blueprint, current_app, g, jsonify, render_template
from flask_restful import reqparse
from omero.gateway.utils import toBoolean

# Global logger for this package
logger = logging.getLogger(__name__)

# Define the blueprint: 'search', set its url
# prefix: app.url/search
search = \
    Blueprint('search', __name__, url_prefix='/search')


def security_filter(event_context):
    """
    Returns a list of `bool` [1] queries that will be combined via a
    `should` occurence type clause with a minimum matches of one.  Each
    is essentially a user "state" with restrictions on the actual OMERO
    data the user has access to.

    This filter does not apply to administrators.  They can see all data on
    the system.

        1. https://www.elastic.co/guide/en/elasticsearch/reference/current/
                query-dsl-bool-query.html
    """
    user_id = event_context.userId
    conditions = [
        # Option 1
        # --------
        #
        # Object IS World Readable.  Never happens in practice but is useful
        # for illustration purposes.
        #
        {
            'bool': {
                'must': [
                    {
                        'term': {
                            'omero:details.permissions.isWorldRead': True
                        }
                    },
                ]
            }
        },
        # Option 2a
        # --------
        #
        # Object IS NOT World Readable but IS Group Readable and the current
        # user is a member of the group which owns the Object.
        #
        {
            'bool': {
                'must': [
                    {
                        'term': {
                            'omero:details.permissions.isWorldRead': False
                        }
                    },
                    {
                        'term': {
                            'omero:details.permissions.iGroupRead': True
                        }
                    },
                    {
                        'nested': {
                            'path': 'omero:details.group.Experimenters',
                            'query': {
                                'term': {
                                    'omero:details.group.Experimenters.@id':
                                        user_id
                                }
                            }
                        }
                    },
                ]
            }
        },
        # Option 2b
        # --------
        #
        # Object IS NOT World Readable and IS NOT Group Readable but the
        # current user is an owner of the group.
        #
        {
            'bool': {
                'must': [
                    {
                        'term': {
                            'omero:details.permissions.isWorldRead': False
                        }
                    },
                    {
                        'term': {
                            'omero:details.permissions.isGroupRead': False
                        }
                    },
                    {
                        'term': {
                            'omero:details.permissions.isUserRead': True
                        }
                    },
                    {
                        'nested': {
                            'path': 'omero:details.group.Experimenters',
                            'query': {
                                'bool': {
                                    'must': [
                                        {
                                            'term': {
                                                'omero:details.group.Experimenters.@id':
                                                    user_id
                                            }
                                        },
                                        {
                                            'term': {
                                                'omero:details.group.Experimenters'
                                                '.omero:isGroupOwner':
                                                    True
                                            }
                                        },
                                    ]
                                }
                            }
                        }
                    },
                ]
            }
        },
        # Option 3
        # --------
        #
        # Object IS NOT World Readable and IS NOT Group Readable but
        # IS User Readable and the current user is the owner of the
        # Object.
        #
        {
            'bool': {
                'must': [
                    {
                        'term': {
                            'omero:details.permissions.isWorldRead': False
                        }
                    },
                    {
                        'term': {
                            'omero:details.permissions.isGroupRead': False
                        }
                    },
                    {
                        'term': {
                            'omero:details.permissions.isUserRead': True
                        }
                    },
                    {
                        'term': {
                            'omero:details.owner.@id': user_id
                        }
                    },
                ]
            }
        },
    ]

    return {
        'bool': {
            'should': [conditions],
            'minimum_should_match': 1
        }
    }


# Views
@search.route('/form/', methods=['GET'])
def load_searching():
    """
    Attempts to be compatible with the `load_searching()` Django view from
    `openmicroscopy/openmicroscopy`.  While it is not 100 percent compatible
    in the HTML it returns it does populate all the data that the user
    interface actually **uses**.
    """
    t0 = time.time()
    try:
        return _load_searching()
    finally:
        logger.debug('Search complete (%dms)' % ((time.time() - t0) * 1000))


def _load_searching():
    event_context = \
        g.omero_client.getSession().getAdminService().getEventContext()
    logger.debug('Event context: %s' % event_context)

    parser = reqparse.RequestParser(bundle_errors=True)
    parser.add_argument(
        'query', required=True,
        help='query string (required)'
    )
    parser.add_argument(
        'batchSize', type=int, dest='batchSize', default=100,
        help='number of elements to return in a single batch (default: 100)'
    )
    parser.add_argument(
        'page', type=int, default=1,
        help='page of elements to return (default: 1)'
    )
    parser.add_argument(
        'datatype', default=['images'], action='append',
        help='OMERO data types to search (default: [\'images\'])'
    )
    parser.add_argument(
        'field', action='append',
        help='fields of data types to filter search by'
    )
    parser.add_argument(
        'searchGroup', help='group to filter search by'
    )
    parser.add_argument(
        'ownedBy', type=int, help='owner to filter search by'
    )
    parser.add_argument(
        'useAcquisitionDate', type=toBoolean,
        help=
            'whether or not to filter by Image acquisition date (True) or '
            'import date (False)'
    )
    parser.add_argument(
        'startdateinput', help='if filtering by date the start date'
    )
    parser.add_argument(
        'enddateinput', help='if filtering by date the end date'
    )    
    args = parser.parse_args()

    # Elasticsearch uses standard offset and limit so we need to convert the
    # page we've been requested to display to an offset.
    _from = (args['page'] - 1) * args['batchSize']
    # If we're an administrator we don't need a security filter.  If we're not
    # we do.
    _filter = dict()
    #if not event_context.isAdmin:
    #    _filter = security_filter(event_context)
    es = Elasticsearch(current_app.config['ELASTICSEARCH_URI'])
    # Prepare a request body for an Elasticsearch "Request Body Search":
    #
    # Reference:
    #   * https://www.elastic.co/guide/en/elasticsearch/reference/current/
    #        search-request-body.html
    body = {
        'from': _from,
        'size': args['batchSize'],
        #'_source': [
        #    'Annotations',
        #],
        # Use the Elasticsearch Query DSL to define our query which must
        # match **any** field and will be filtered by our security filter.
        #
        # Reference:
        #   * https://www.elastic.co/guide/en/elasticsearch/reference/
        #       current/query-dsl.html
        'query': {
            'bool': {
                'should': [
                    # Match the Project-Dataset hierarchy itself
                    {
                        'match': {
                            '_all': args['query']
                        }
                    },
                    # Match the image children
                    #
                    # Reference:
                    #   * https://www.elastic.co/guide/en/elasticsearch/
                    #       reference/current/query-dsl-has-child-query.html
                    #{
                    #    'has_child': {
                    #        'type': 'image',
                    #        'query': {
                    #            'match': {
                    #                '_all': args['query']
                    #            }
                    #        }
                    #    }
                    #},
                ],
                'filter': _filter,
                'minimum_should_match': 1
            }
        },
        # Sort by score.
        #
        # Reference:
        #   * https://www.elastic.co/guide/en/elasticsearch/reference/
        #       current/search-request-sort.html
        'sort': [
            #{
            #    'Annotations.TimeValue': {
            #        'order': 'desc',
            #        'mode': 'max',
            #        'nested_path': 'Annotations',
            #        'nested_filter': {
            #            'match': {
            #                'Annotations.Namespace':
            #                    'com.glencoesoftware.journal_bridge:'
            #                    'publicationDate'
            #            }
            #        }
            #    }
            #},
            '_score'
        ]
    }
    result = es.search(
        index=current_app.config['ELASTICSEARCH_INDEX'],
        #doc_type='manuscript',
        body=body
    )
    logger.debug('Result: %s' % pformat(result, indent=2))

    # Prepare the entire search result wide data for `load_searching()`
    # view compatibility
    ctx = {
        'result': result
    }
    return render_template('search_details.html', **ctx)
