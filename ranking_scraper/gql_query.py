""" Utility class to construct GraphQL queries without requiring model definition. """

# TODO: Could be useful to other people, factor out to separate project with proper unit testing?
# Feature list, in order of importance:
# 1. Ability to construct basic query with fields and arguments
# 2. Aliases
# 3. Mutations (Should be pretty straightforward?)
# 4. Pretty print queries (ability to customise print output for display / debug purposes)
# 5. Fragments support in some way (as_fragment maybe?)
# Below is probably not necessary since we can just use our builder to do these
# 6. Variable inserts
# 7. Directives

import typing
from datetime import datetime
from pprint import pprint as pp


class GraphQLQuery(object):
    def __init__(self, query_name='Query'):
        """
        :param query_name: Name of the query. Purely for clarity purposes. Default: "Query".
        :type query_name: str
        """
        self.query_name = query_name
        self._fields: typing.Dict[str, GraphQLField] = dict()

    def build(self):
        """

        :return:
        :rtype: str
        """
        return f'query {self.query_name}{{{",".join(f.build() for f in self._fields.values())}}}'

    def field(self, name):
        """

        :param name:
        :return:
        :rtype: GraphQLField
        """
        if name not in self._fields:
            self._fields[name] = GraphQLField(field_name=name)
        return self._fields[name]

    f = fld = field  # Shortcut definitions

    def fields(self, *field_names):
        """
        Convenience method to specify multiple fields.

        :return: This instance for method chaining.
        :rtype: GraphQLQuery
        """
        for f in field_names:
            self.field(name=f)
        return self

    def __contains__(self, item):
        if not isinstance(item, (str, GraphQLField,)):
            raise TypeError(f'Expected a GraphQLField or its name (str). Got {item} instead.')
        if isinstance(item, str):
            return item in self._fields
        return item in self._fields.values()

    def __repr__(self):
        """ A basic representation of the query. """
        # TODO: Implementation assumes ',', '{', and '}' are not present within data!
        # TODO: Implementation not adjustable
        q_str = self.build()
        q_str = q_str.replace('{', '{\n').replace('}', '\n}').replace(',', ',\n')
            # .replace('(', '(\n').replace(')', ')\n')
        lines = q_str.split('\n')
        indent = 0
        new_lines = list()
        for line in lines:
            # Remove indentation __before__ print if end of indentation
            if line.startswith('}'):
                indent -= 2
            new_lines.append(f'{" "*indent}{line}')
            if line.endswith('{'):
                indent += 2
        return '\n'.join(new_lines)


class GraphQLField(object):
    def __init__(self, field_name):
        self.name = field_name
        self._fields = dict()
        self.params = dict()

    def field(self, name):
        """
        Define a field to be retrieved and returns the representative GraphQLField instance.

        If it was already defined previously, returns that field.

        :rtype: GraphQLField
        """
        if name not in self._fields:
            self._fields[name] = GraphQLField(field_name=name)
        return self._fields[name]

    f = fld = field  # Shortcut definitions

    def add_fields(self, *field_names):
        """
        Convenience method to specify multiple fields.

        :return: This instance for method chaining.
        :rtype: GraphQLField
        """
        for f in field_names:
            self.field(name=f)
        return self

    def add_params(self, **kwargs):
        """
        Set / update parameter values. Return this field for chaining.

        :return: This instance for method chaining.
        :rtype: GraphQLField
        """
        self.params.update(kwargs)
        return self

    def build(self):
        """

        :return:
        :rtype: str
        """
        result = self.name
        if self.params:
            param_string = ', '.join((f'{k}: {self._sanitize_value(v)}'
                                      for k, v in self.params.items()))
            result += '(' + param_string + ')'
        if not self._fields:
            return result
        result += f'{{{",".join(f.build() for f in self._fields.values())}}}'
        return result

    def _sanitize_value(self, value):
        """
        Return the correct string format of a value for use in a GraphQL query string.
        """
        # TODO: Add support for the other built-in types.
        # TODO: None --> null?
        if isinstance(value, bool):  # Note: bool check must be before int/float!
            return f'{str(value).lower()}'
        if isinstance(value, (int, float)):
            return f'{value}'
        if isinstance(value, (list,)):
            return f'[{", ".join(self._sanitize_value(v) for v in value)}]'
        if isinstance(value, dict):
            result = '{'
            # TODO: Filter out None values?
            result += ", ".join(f'{k}: {self._sanitize_value(v)}' for k, v in value.items())
            result += '}'
            return result
        # Assumed has to be enclosed (eg. for strings, maybe also datetime?)
        return f'"{value}"'

    def __contains__(self, item):
        if not isinstance(item, (str, GraphQLField,)):
            raise TypeError(f'Expected a GraphQLField or its name (str). Got {item} instead.')
        if isinstance(item, str):
            return item in self._fields
        return item in self._fields.values()


# Some reference gql queries:
"""
query TournamentsByCountryPaging($countryCode: String!, $afterDate: Timestamp!, $perPage: Int!) {
  tournaments(query: {
    perPage: $perPage
    filter: {
      countryCode: $countryCode
      videogameIds: [1386]
      upcoming: false
      hasOnlineEvents: false
      afterDate: $afterDate
    }
  }) {
    pageInfo {
      totalPages
      perPage
    }
  }
}
"""


def test_run():
    # --- Page info
    # query = GraphQLQuery()
    # query.field('tournaments') \
    #     .params(query=dict(perPage=25,
    #                        filter=dict(videogameIds=[1386],
    #                                    hasOnlineEvents=False,
    #                                    countryCode='BE',
    #                                    upcoming=False,
    #                                    afterDate=int(datetime(year=2019,
    #                                                           month=1,
    #                                                           day=1).timestamp()))
    #                        )) \
    #     .field('pageInfo') \
    #     .fields(['totalPages', 'perPage'])
    # print(query.build())
    # --- Tournament page retrieval
    query = GraphQLQuery()
    query.field('tournaments') \
        .add_params(query=dict(page=1,
                               perPage=25,
                               filter=dict(videogameIds=[1386],
                                       hasOnlineEvents=False,
                                       countryCode='BE',
                                       upcoming=False,
                                       afterDate=int(datetime(year=2019,
                                                              month=1,
                                                              day=1).timestamp()))
                               )) \
        .field('nodes') \
        .add_fields('id',
                 'name',
                 'countryCode',
                 'endAt')
    query.field('tournaments').f('nodes').f('events').add_fields('id',
                                                              'name',
                                                              'isOnline',
                                                              'numEntrants',
                                                              'state',
                                                              'type')
    query.f('tournaments').f('nodes').f('events').f('videogame').f('id')
    print(query.build())
    print(query)
    # --- Basic lookup
    # query = GraphQLQuery()
    # query.field('player').params(id=642186).field('gamerTag')
    # pp(query.build())


if __name__ == '__main__':
    test_run()
