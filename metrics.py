# -*- coding: utf-8 -*-
# Upside Travel, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import requests

from datetime import datetime
from pytz import timezone

import datadog
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED

from common import SLACK_NOTIFICATION_WEBHOOK_URL
from common import SLACK_NOTIFICATION_ON_CLEAN
from common import str_to_bool


def send(env, bucket, key, status):
    if "DATADOG_API_KEY" in os.environ:
        datadog.initialize()  # by default uses DATADOG_API_KEY

        result_metric_name = "unknown"

        metric_tags = ["env:%s" % env, "bucket:%s" % bucket, "object:%s" % key]

        if status == AV_STATUS_CLEAN:
            result_metric_name = "clean"
        elif status == AV_STATUS_INFECTED:
            result_metric_name = "infected"
            datadog.api.Event.create(
                title="Infected S3 Object Found",
                text="Virus found in s3://%s/%s." % (bucket, key),
                tags=metric_tags,
            )

        scanned_metric = {
            "metric": "s3_antivirus.scanned",
            "type": "counter",
            "points": 1,
            "tags": metric_tags,
        }
        result_metric = {
            "metric": "s3_antivirus.%s" % result_metric_name,
            "type": "counter",
            "points": 1,
            "tags": metric_tags,
        }
        print("Sending metrics to Datadog.")
        datadog.api.Metric.send([scanned_metric, result_metric])


def slack_notification(env, bucket, key, status):
    current_time = datetime.now(timezone("Australia/Sydney")).strftime("%m-%d-%Y %H:%M:%S")
    alert_map = {
        "message": {
            AV_STATUS_CLEAN: ":white_check_mark: :white_check_mark: :white_check_mark: New Scan Result: CLEAN :white_check_mark: :white_check_mark: :white_check_mark:",
            AV_STATUS_INFECTED: ":space_invader: :space_invader: :space_invader: New Scan Result: INFECTED :space_invader: :space_invader: :space_invader:"
        },
        "color": {
            AV_STATUS_CLEAN: "#32a852",
            AV_STATUS_INFECTED: "#ad1721"
        },
        "image": {
            AV_STATUS_CLEAN: "https://emojis.slackmojis.com/emojis/images/1588863770/8928/space-invader-green.png",
            AV_STATUS_INFECTED: "https://emojis.slackmojis.com/emojis/images/1588863793/8929/space-invader-orange.png"
        }
    }

    if SLACK_NOTIFICATION_WEBHOOK_URL is not None:
        # Early return if result is clean and SLACK_NOTIFICATION_ON_CLEAN is false
        if status == AV_STATUS_CLEAN and not str_to_bool(SLACK_NOTIFICATION_ON_CLEAN):
            return

        data = {
            "attachments": [
                {
                    "mrkdwn_in": ["text"],
                    "color": alert_map["color"][status],
                    "author_name": "ClamAV Scan",
                    "author_link": "https://www.clamav.net/",
                    "author_icon": "https://www.clamav.net/assets/clamav-trademark.png",
                    "fields": [
                        {
                            "title": "Bucket",
                            "value": bucket,
                            "short": False
                        },
                        {
                            "title": "When",
                            "value": current_time,
                            "short": False
                        },
                        {
                            "title": "Key",
                            "value": key,
                            "short": True
                        },
                        {
                            "title": "Status",
                            "value": status,
                            "short": True
                        }
                    ],
                    "thumb_url": alert_map["image"][status],
                }
            ]
        }

        r = requests.post(SLACK_NOTIFICATION_WEBHOOK_URL, json=data)
        return r.status_code
