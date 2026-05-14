import sys
from os.path import dirname, join
sys.path.insert(0, join(dirname(__file__), '..'))
from outreach.tracking import OutreachManager, LeadTracking, OUTREACH_TEMPLATES, generate_personalized_message
