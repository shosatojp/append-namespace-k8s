import yaml
import argparse
import sys
from kubernetes import client, config
import requests


def get_resources(groupVersion, configuration: client.Configuration):
    res = requests.get(f'{configuration.host}/apis/{groupVersion}', headers={
        'Authorization': configuration.api_key['authorization']
    }, verify=False)

    if res.status_code == 200:
        return res.json()
    else:
        raise RuntimeError(f'Failed to get resources: {groupVersion}')


def get_apis(configuration: client.Configuration):
    res = requests.get(configuration.host + '/apis', headers={
        'Authorization': configuration.api_key['authorization']
    }, verify=False)
    if res.status_code == 200:
        return res.json()
    else:
        raise RuntimeError('Failed to get apis')


def create_namespaced_map(configuration: client.Configuration):
    apigroup_map = dict()
    groups = get_apis(configuration)['groups']
    for group in groups:
        for version in group['versions']:
            groupVersion = version['groupVersion']
            apigroup_map[groupVersion] = dict()
            resources = get_resources(groupVersion, configuration)['resources']
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
    args = parser.parse_args()

    # Existent resources from api server
    configuration = client.Configuration()
    config.load_kube_config(client_configuration=configuration)
    namespaced_map = create_namespaced_map(configuration)

    with open(args.file, 'rt', encoding='utf-8') as f:
        docs = list(yaml.load_all(f))

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
        if '/' not in apiVersion:
            apiVersion = f'apps/{apiVersion}'
        namespace = doc.get('metadata', {}).get('namespace', None)

        if namespace and namespace != args.namespace:
            if input('Another namespace found(Y/n)') == 'n':
                print('skip')
                continue

        if (not namespace or args.overwrite) and namespaced_map[apiVersion]:
            doc['metadata'] = doc.get('metadata', {})
            doc['metadata']['namespace'] = args.namespace

    yaml.dump_all(docs, sys.stdout)


if __name__ == '__main__':
    main()
