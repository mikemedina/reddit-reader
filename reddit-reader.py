import json
import logging
import requests
import time
import unidecode


USERNAME = ''
PASSWORD = ''

ISP_URL = 'https://api.amazonalexa.com/v1/users/~current/skills/~current/inSkillProducts'

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_reddit_posts(subreddit, number_of_posts):
    """Get posts from the given subreddit."""
    reddit_login_data = {
        'user': USERNAME,
        'password': PASSWORD,
        'api_type': 'json'
    }
    session = requests.Session()
    session.headers.update({'User-Agent': f'I am testing Alexa: {USERNAME}'})
    session.post('https://www.reddit.com/api/login', data = reddit_login_data)

    time.sleep(1)

    url = f'https://reddit.com/r/{subreddit}/.json?limit={number_of_posts}'
    data = json.loads(session.get(url).content.decode('utf-8'))

    titles = [unidecode.unidecode(listing['data']['title']) for listing in data['data']['children']]
    return '... '.join([title for title in titles])

def present_headlines(subreddit, number_of_posts):
    """Return a user-friendly string containing the top posts from the given subreddit."""
    reddit_posts = get_reddit_posts(subreddit, number_of_posts)
    return f'Here are the top {number_of_posts} posts from are slash {subreddit}: {reddit_posts}'

def get_isp_info(api_access_token):
    """Fetch the current in-skill-purchase information."""
    headers = {'Accept-Language': 'en-US', 'Authorization': f'bearer {api_access_token}'}
    isp_response = requests.get(ISP_URL, headers=headers)
    return isp_response.json()

def get_api_access_token(context):
    """Get the API access token from the current request context."""
    return context['System']['apiAccessToken']

def is_entitled_to_subreddit_requests(context):
    """Determine whether or not the current user is entitled to subreddit requests."""
    api_access_token = get_api_access_token(context)
    isp_info = get_isp_info(api_access_token)

    try:
        entitled_property = isp_info['inSkillProducts'][0]['entitled']
    except KeyError:
        return False

    return entitled_property == 'ENTITLED'

def get_product_id(context):
    """Get the product_id from the current context."""
    api_access_token = get_api_access_token(context)
    isp_info = get_isp_info(api_access_token)
    return isp_info['inSkillProducts'][0]['productId']

def build_response(
        title=None,
        output=None,
        reprompt_text=None,
        should_end_session=True,
        session_attributes=None,
        directives=None):
    """Build the reponse."""
    response = {}
    body = {}
    # Add speech output
    if output:
        response['outputSpeech'] = {
            'type': 'PlainText',
            'text': output
        }

    # Add a card
    if output and title:
        response['card'] = {
            'type': 'Simple',
            'title': f'{title}',
            'content': f'{output}'
        }

    # Add a reprompt
    if not reprompt_text:
        reprompt_text = output

    response['reprompt'] = {
        'outputSpeech': {
            'type': 'PlainText',
            'text': reprompt_text
        }
    }

    # Add directives
    if directives:
        response['directives'] = directives

    if session_attributes:
        body['sessionAttributes'] = session_attributes

    body['version'] = '1.0'
    body['shouldEndSession'] = should_end_session
    body['response'] = response
    return body

def get_welcome_response():
    """Build the response returned when the skill is launched."""
    title = 'Welcome to reddit reader'
    output = 'Welcome to reddit reader, your one-stop-shop for reading reddit'
    return build_response(title=title, output=output)

def get_read_intent_response():
    """Build the response returned when the read intent is launched."""
    title=title = 'Thanks for reading from reddit!'
    output=output = present_headlines('all', 5)
    return build_response(title=title, output=output)

def get_read_from_intent_response(subreddit):
    """Build the response returned when the read_from intent is launched."""
    title=title = f'Thanks for reading from r/{subreddit}'
    output=output = present_headlines(subreddit, 5)
    return build_response(title=title, output=output)

def get_buy_subreddit_requests_directive(product_id):
    """Build the directive portion of the response for when the buy_subreddit_requests intent is launched."""
    return  [{
        'type': 'Connections.SendRequest',
        'name': 'Buy',
        'payload': {
            'InSkillProduct': {
                'productId': product_id
            }
        },
        'token': 'BUY'
    }]

def get_subreddit_requests_upsell_directive(product_id):
    """Build the directive portion of the response for when the buy_subreddit_requests_upsell response is returned."""
    return  [{
        'type': 'Connections.SendRequest',
        'name': 'Upsell',
        'payload': {
            'InSkillProduct': {
                'productId': product_id
            },
            'upsellMessage': "Subreddit requests lets you request whatever subreddit you'd like. Do you want to purchase this functionality?"
        },
        'token': 'UPSELL'
    }]

def get_refund_subreddit_requests_directive(product_id):
    """Build the directive portion of the response for when the refund_subreddit_requests response is returned."""
    return  [{
        'type': 'Connections.SendRequest',
        'name': 'Cancel',
        'payload': {
            'InSkillProduct': {
                'productId': product_id
            },
        },
        'token': 'REFUND'
    }]
    
def get_subreddit_request_upsell_response(context):
    """Build the response for when a user tries to use subreddit requests but isn't entitled."""
    title=title = "Subreddit requests aren't enabled"
    output=output = "Sorry, you don't have subreddit requests enabled yet"

    product_id = get_product_id(context)
    directives = get_subreddit_requests_upsell_directive(product_id)
    return build_response(title=title, output=output, directives=directives)

def get_buy_subreddit_requests_response(context):
    """Build the response returned when a user purchases subreddit requests."""
    entitled_to_subreddit_requests = is_entitled_to_subreddit_requests(context)

    if entitled_to_subreddit_requests:
        title=title = 'Subreddit requests are already enabled'
        output=output = "You've already enabled subreddit requests"
        directives = None
    else:
        title=title = 'Thanks for enabling subreddit requests!'
        output=output = 'Thank you so much for enabling subreddit requests! Enjoy!'

        product_id = get_product_id(context)
        directives = get_buy_subreddit_requests_directive(product_id)
    return build_response(title=title, output=output, directives=directives)

def get_refund_subreddit_requests_response(context):
    """Build the response returned when a user refunds subreddit requests."""
    entitled_to_subreddit_requests = is_entitled_to_subreddit_requests(context)

    if entitled_to_subreddit_requests:
        product_id = get_product_id(context)
        directives = get_refund_subreddit_requests_directive(product_id)
    else:
        directives = None

    return build_response(directives=directives)

def handle_session_end_request():
    """Build the response for a terminated session."""
    title=title = 'Session Ended'
    output=output = 'Thank you for using reddit reader'

    return build_response(title=title, output=output)

def on_launch(launch_request, context):
    """Start the skill with the default behavior."""
    return get_welcome_response()

def on_intent(intent, context):
    """Handle intent dispatching."""
    intent_name = intent['name']

    if intent_name == 'read':
        response = get_read_intent_response()
        logger.info(f'\n\n{intent_name} response: ' + json.dumps(response, indent=4, sort_keys=True))
        return response
    elif intent_name == 'read_from':
        subreddit = intent['slots']['subreddit']['value']

        if is_entitled_to_subreddit_requests(context):
            response = get_read_from_intent_response(subreddit) 
        else:
            response = get_subreddit_request_upsell_response(context)

        logger.info(f'\n\n{intent_name} response: ' + json.dumps(response, indent=4, sort_keys=True))
        return response
    elif intent_name == 'buy_subreddit_request':
        response = get_buy_subreddit_requests_response(context)
        logger.info(f'\n\n{intent_name} response: ' + json.dumps(response, indent=4, sort_keys=True))
        return response
    elif intent_name == 'refund_subreddit_requests':
        response = get_refund_subreddit_requests_response(context)
        logger.info(f'\n\n{intent_name} response: ' + json.dumps(response, indent=4, sort_keys=True))
        return response
    elif intent_name == 'AMAZON.HelpIntent':
        response = get_welcome_response()
        logger.info(f'\n\n{intent_name} response: ' + json.dumps(response, indent=4, sort_keys=True))
        return response
    elif intent_name == 'AMAZON.CancelIntent' or intent_name == 'AMAZON.StopIntent':
        response = handle_session_end_request()
        logger.info(f'\n\n{intent_name} response: ' + json.dumps(response, indent=4, sort_keys=True))
        return response
    else:
        raise ValueError(f'Invalid intent type: {intent_name}')

def on_session_ended(session_ended_request, context):
    """Handle session clean up when the session should end."""
    pass

def on_purchase_flow(request, context):
    """Handle purchase flow response scenarios."""
    purchase_result = request['payload']['purchaseResult']
    if purchase_result == 'ACCEPTED':
        if request['token'] == 'REFUND':
            title=title = "Sorry it wasn't what you hoped"
            output=output = "Sorry subreddit requests wasn't what you were after."
        else:
            title=title = "You've enabled subreddit requests!"
            output=output = 'Now you can request to read from any of the top 1000 subreddits!'
    elif purchase_result == 'DECLINED':
        title=title = 'Maybe later'
        output=output = 'No problem, you can ask about subreddit requests again any time.'
    elif purchase_result == 'ALREADY_PURCHASED':
        title=title = 'Subreddit requests are already enabled'
        output=output = "You've already got access to subreddit requests"
    else:
        title=title = 'Something went wrong while purchasing subreddit requests'
        output=output = "I'm sorry, something went wrong while purchasing subreddit requests. Check your payment information on your Amazon account and try again."

    return build_response(title=title, output=output)

def lambda_handler(event, context):
    """Route the incoming request based on type (LaunchRequest, IntentRequest, etc.)
    The JSON body of the request is provided in the event parameter.
    """
    request_type = event['request']['type']
    if request_type == 'LaunchRequest':
        return on_launch(event['request'], event['context'])
    elif request_type == 'IntentRequest':
        return on_intent(event['request']['intent'], event['context'])
    elif request_type == 'Connections.Response':
        return on_purchase_flow(event['request'], event['context'])
    elif request_type == 'SessionEndedRequest':
        on_session_ended(event['request'], event['context'])
    else:
        raise ValueError('Invalid request type')

if __name__ == '__main__':
    print('mike rules')

