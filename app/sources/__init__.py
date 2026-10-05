from .demo import DemoSource
from .greenhouse import GreenhouseSource
from .jobspy_source import JobSpySource
from .jsonld import JSONLDSource
from .lever import LeverSource
from .rss import RSSSource
from .smartrecruiters import SmartRecruitersSource
from .public_boards import LinkedInSource, ApecSource, WttjSource, CyberSecurityJobsiteSource

ADAPTERS = {
    "linkedin": LinkedInSource,
    "apec": ApecSource,
    "wttj": WttjSource,
    "cybersecurityjobsite": CyberSecurityJobsiteSource,
    "smartrecruiters": SmartRecruitersSource,
    "demo": DemoSource,
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "rss": RSSSource,
    "jsonld": JSONLDSource,
    "jobspy": JobSpySource,
}
