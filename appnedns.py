import yaml
import argparse
import sys
from kubernetes import client, config
import requests

insecure = False
configuration = client.Configuration()


def call_api(url):
    res = requests.get(url, headers={
        'Authorization': configuration.api_key['authorization']
    }, verify=not insecure)

    if res.status_code == 200:
        return res.json()
    else:
        raise RuntimeError(f'Failed to get resources: {url}')


def get_resources(groupVersion):
    return call_api(f'{configuration.host}/apis/{groupVersion}')


def get_core_resources(version):
    return call_api(f'{configuration.host}/api/{version}')


def get_coreapi():
    return call_api(configuration.host + '/api')


def get_apis():
    return call_api(configuration.host + '/apis')


def create_namespaced_map():
    apigroup_map = dict()

    coreapi = get_coreapi()
    versions = coreapi['versions']
    for version in versions:
        apigroup_map[version] = dict()
        resources = get_core_resources(version)['resources']
        for resource in resources:
            kind = resource['kind']
            namespaced = resource['namespaced']
            apigroup_map[version][kind] = namespaced

    groups = get_apis()['groups']
    for group in groups:
        for version in group['versions']:
            groupVersion = version['groupVersion']
            apigroup_map[groupVersion] = dict()
            resources = get_resources(groupVersion)['resources']
            for resource in resources:
                kind = resource['kind']
                namespaced = resource['namespaced']
                apigroup_map[groupVersion][kind] = namespaced
    return apigroup_map


def parse_crd(crd):
    group = crd['spec']['group']
    kind = crd['spec']['names']['kind']
    namespaced = crd['spec']['scope'] == 'Namespaced'
    versions = crd['spec']['versions']
    for version in versions:
        version_name = version['name']
        yield (f'{group}/{version_name}', kind, namespaced)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True)
    parser.add_argument('-n', '--namespace', required=True)
    parser.add_argument('--overwrite', action='store_true', default=False)
    parser.add_argument('--insecure', action='store_true', default=False)
    args = parser.parse_args()
    global insecure
    global configuration
    insecure = args.insecure

    # Existent resources from api server
    config.load_kube_config(client_configuration=configuration)
    namespaced_map = create_namespaced_map()

    with open(args.file, 'rt', encoding='utf-8') as f:
        docs = list(yaml.load_all(f, Loader=yaml.FullLoader))

    # CRDs
    for doc in docs:
        apiVersion, kind = doc.get('apiVersion', None), doc.get('kind', None)
        if kind == 'CustomResourceDefinition':
            for version_tuple in parse_crd(doc):
                apiVersion, kind, namespaced = version_tuple
                namespaced_map[apiVersion] = namespaced_map.get(apiVersion, {})
                namespaced_map[apiVersion][kind] = namespaced

    # append namespace
    for doc in docs:
        apiVersion, kind = doc.get('apiVersion', None), doc.get('kind', None)
        namespace = doc.get('metadata', {}).get('namespace', None)

        if namespace and namespace != args.namespace:
            if input('Another namespace found(Y/n)') == 'n':
                print('skip')
                continue

        if (not namespace or args.overwrite) and namespaced_map[apiVersion][kind]:
            doc['metadata'] = doc.get('metadata', {})
            doc['metadata']['namespace'] = args.namespace

    # check if docs contains namespace resource
    contains_namespace = False
    for doc in docs:
        apiVersion, kind = doc.get('apiVersion', None), doc.get('kind', None)
        contains_namespace = contains_namespace or kind == 'Namespace'
    if not contains_namespace:
        print('You may need to create Namespace resource.', file=sys.stderr)

        print('---', file=sys.stderr)
        print('apiVersion: v1', file=sys.stderr)
        print('kind: Namespace', file=sys.stderr)
        print('metadata:', file=sys.stderr)
        print('  name: ' + args.namespace, file=sys.stderr)
        print('---', file=sys.stderr)

    yaml.dump_all(docs, sys.stdout)


if __name__ == '__main__':
    main()
