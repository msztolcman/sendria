import pkg_resources


def get_version():
    try:
        return 'v' + pkg_resources.get_distribution('mailtrap').version
    except pkg_resources.DistributionNotFound:
        return 'dev'
