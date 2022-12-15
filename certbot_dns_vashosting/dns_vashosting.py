import json
import logging

from typing import Any
from typing import Callable
from typing import Optional

import zope.interface

from certbot.interfaces import IAuthenticator, IPluginFactory

import requests

from certbot import errors
from certbot.plugins import dns_common
from certbot.plugins.dns_common import CredentialsConfiguration

logger = logging.getLogger(__name__)


@zope.interface.implementer(IAuthenticator)
@zope.interface.provider(IPluginFactory)
class Authenticator(dns_common.DNSAuthenticator):
    description = "Obtain certificates using a DNS TXT record (if you are using Vashosting.cz " \
                  "vps centrum REST API for DNS). "
    ttl = 60

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.credentials: Optional[CredentialsConfiguration] = None

    @classmethod
    def add_parser_arguments(cls, add: Callable[..., None],
                             default_propagation_seconds: int = 1800) -> None:
        super().add_parser_arguments(add, default_propagation_seconds)
        add('credentials', help='Vashosting.cz credentials INI file.')

    def more_info(self) -> str:
        return (
                "This plugin configures a DNS TXT record to respond to a dns-01 challenge using "
                + "the Vas-hosting.cz vps centrum Remote REST API."
        )

    def _setup_credentials(self):
        self.credentials = self._configure_credentials(
            "credentials",
            "Vashosting.cz credentials INI file",
            {
                "endpoint": "URL of the Vashosting.cz Remote API. Eg: "
                            "https://xxxx.vas-server.cz/admin/api/v1/api.php",
                "admin": "Admin user for Vashosting.cz Remote API.",
                "api-key": "Api key for Vashosting.cz Remote API.",
            },
        )

    def _perform(self, domain, validation_name, validation):
        self._get_vashosting_api_client().add_txt_record(
            domain, validation_name, validation, self.ttl
        )

    def _cleanup(self, domain, validation_name, validation):
        self._get_vashosting_api_client().del_txt_record(
            domain, validation_name, validation, self.ttl
        )

    def _get_vashosting_api_client(self):
        return _VasHostingRestApiClient(
            self.credentials.conf("endpoint"),
            self.credentials.conf("admin"),
            self.credentials.conf("api-key"),
        )


class _VasHostingRestApiClient(object):
    def __init__(self, endpoint, admin, apiKey):
        logger.debug("creating vashosting rest api client")
        self.endpoint = endpoint
        self.adminEmail = admin
        self.apiKey = apiKey
        self.session = requests.Session()
        self.session_id = None

    def _api_request(self, action, data, response_is_json=False):
        if self.session_id is not None:
            data["session_id"] = self.session_id
        data['command'] = action

        headers = {'content-type': 'application/json', 'x-vpsc-admin': self.adminEmail,
                   'x-vpsc-apikey': self.apiKey}

        url = self._get_url(action)
        resp = self.session.post(url, json=data, headers=headers)
        logger.info("API Request to URL: %s", url)
        logger.info("Data: %s", data)
        logger.info("Headers: %s", headers)
        if resp.status_code != 200:
            raise errors.PluginError(
                "HTTP Error during login {0} - {1}".format(resp.status_code, resp.content)
            )

        if response_is_json:
            try:
                result = resp.json()
            except json.decoder.JSONDecodeError:
                raise errors.PluginError(
                    "API response with non JSON: {0}".format(resp.text)
                )

            return result
        else:
            return resp.content

    def _get_url(self, action):
        return "{0}?{1}".format(self.endpoint, action)

    def add_txt_record(self, domain, record_name, record_content, record_ttl):
        """
        Add a TXT record using the supplied information.
        :param str domain: The domain to use to look up the managed zone.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        :param int record_ttl: The record TTL (number of seconds that the record may be cached).
        :raises certbot.errors.PluginError: if an error occurs communicating with the ISPConfig API
        """
        logger.info(
            "using domain: %s and record_name: %s. Content is: %s", domain, record_name,
            record_content
        )
        record = self.get_existing_txt(domain, record_name)
        if record is not None:
            if record["value"] == record_content:
                logger.info("already there, current value: %s is same as wanted", record["value"])
                return
            else:
                logger.info("update {0}".format(record["id"]))
                self._delete_txt_record(domain, record["id"])  # has to delete, because of api
                self._update_txt_record(
                    domain, record_name, record_content, record_ttl
                )
        else:
            logger.info("insert new txt record")
            self._insert_txt_record(domain, record_name, record_content, record_ttl)

    def prepare_record_name(self, domain, record_name):
        return record_name.replace("." + domain, "")

    def del_txt_record(self, domain, record_name, record_content, record_ttl):
        """
        Delete a TXT record using the supplied information.
        :param str domain: The domain to use to look up the managed zone.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        :param int record_ttl: The record TTL (number of seconds that the record may be cached).
        :raises certbot.errors.PluginError: if an error occurs communicating with the ISPConfig API
        """
        logger.info(
            "using domain: %s and record_name: %s. Content is: %s", domain, record_name,
            record_content
        )
        record = self.get_existing_txt(domain, record_name)
        if record is not None:
            if record["value"] == record_content:
                logger.info("delete TXT record: %s", record)
                self._delete_txt_record(domain, record["id"])

    def _insert_txt_record(self, domain, record_name, record_content, record_ttl):
        record_name = self.prepare_record_name(domain, record_name)
        data = {"domain": domain, 'record': record_name, 'value': record_content, 'type': "TXT"}
        logger.info("insert with data: %s", data)
        self._api_request("dns-add-record", data)

    def _update_txt_record(
            self, domain, record_name, record_content, record_ttl
    ):
        o_record_name = record_name
        record_name = self.prepare_record_name(domain, record_name)
        data = {"domain": domain, 'record': record_name, 'value': record_content, 'type': "TXT"}
        logger.info("update with data: %s", data)
        self._api_request("dns-add-record", data)

    def _delete_txt_record(self, domain, id):
        data = {"id": id, "domain": domain}
        logger.info("delete with data: %s", data)
        self._api_request("dns-delete-record", data)

    def get_existing_txt(self, domain, record_name):
        """
        Get existing TXT records from the RRset for the record name.
        If an error occurs while requesting the record set, it is suppressed
        and None is returned.
        :param str domain: The ID of the managed zone.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :returns: TXT record value or None
        :rtype: `string` or `None`
        """
        commandData = {"domain": domain}
        zone_data = self._api_request("dns-list-records", commandData, True)
        for entry in zone_data.values():
            logger.info(entry)
            if (
                    entry["record"] == record_name
                    and entry["type"] == "TXT"
            ):
                value = entry["value"]  # type: str
                if value.startswith("\""):
                    value = value.replace("\"", "")

                entry["value"] = value
                return entry
        return None
