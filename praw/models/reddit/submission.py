"""Provide the Submission class."""
from six.moves.urllib.parse import (urljoin,  # pylint: disable=import-error
                                    urlparse)

from ...const import API_PATH
from ...exceptions import ClientException
from ..comment_forest import CommentForest
from ..listing.mixins import SubmissionListingMixin
from .base import RedditBase
from .mixins import UserContentMixin
from .redditor import Redditor
from .subreddit import Subreddit


class Submission(RedditBase, SubmissionListingMixin, UserContentMixin):
    """A class for submissions to reddit."""

    EQ_FIELD = 'id'

    @staticmethod
    def id_from_url(url):
        """Return the ID contained within a submission URL.

        :param url: A url to a submission in one of the following formats (http
            urls will also work):
            * https://redd.it/2gmzqe
            * https://reddit.com/comments/2gmzqe/
            * https://www.reddit.com/r/redditdev/comments/2gmzqe/praw_https/

        Raise ``ClientException`` if URL is not a valid submission URL.

        """
        parsed = urlparse(url)
        if not parsed.netloc:
            raise ClientException('Invalid URL: {}'.format(url))

        parts = parsed.path.split('/')
        if 'comments' not in parts:
            submission_id = parts[-1]
        else:
            submission_id = parts[parts.index('comments') + 1]

        if not submission_id.isalnum():
            raise ClientException('Invalid URL: {}'.format(url))
        return submission_id

    def __init__(self, reddit, id=None,  # pylint: disable=redefined-builtin
                 url=None, _data=None):
        """Initialize a Submission instance.

        :param reddit: An instance of :class:`~.Reddit`.
        :param id: A reddit base64 submission ID, e.g., ``2gmzqe``.
        :param url: A URL supported by :meth:`~.id_from_url`.

        Either ``id`` or ``url`` can be provided, but not both.

        """
        if [id, url, _data].count(None) != 2:
            raise TypeError('Exactly one of `id`, `url`, or `_data` must be '
                            'provided.')
        super(Submission, self).__init__(reddit, _data)
        self.comment_limit = 2048
        self.comment_sort = 'best'
        if id is not None:
            self.id = id  # pylint: disable=invalid-name
        elif url is not None:
            self.id = self.id_from_url(url)
        self.flair = SubmissionFlair(self)
        self.mod = SubmissionModeration(self)

    def __setattr__(self, attribute, value):
        """Objectify author, comments, and subreddit attributes."""
        # pylint: disable=redefined-variable-type
        if attribute == 'author':
            value = Redditor.from_data(self._reddit, value)
        elif attribute == 'subreddit':
            value = Subreddit(self._reddit, value)
        super(Submission, self).__setattr__(attribute, value)

    def _fetch(self):
        other, comments = self._reddit.get(self._info_path(),
                                           params={'limit': self.comment_limit,
                                                   'sort': self.comment_sort})
        other = other.children[0]
        other.comments = CommentForest(self)
        self.__dict__.update(other.__dict__)
        self.comments._update(comments.children)
        self._fetched = True

    def _info_path(self):
        return API_PATH['submission'].format(id=self.id)

    def hide(self):
        """Hide Submission."""
        self._reddit.post(API_PATH['hide'], data={'id': self.fullname})

    def set_flair(self, *args, **kwargs):
        """Set flair for this submission.

        Convenience function that utilizes :meth:`.ModFlairMixin.set_flair`
        populating both the `subreddit` and `item` parameters.

        :returns: The json response from the server.

        """
        return self.subreddit.set_flair(self, *args, **kwargs)

    @property
    def shortlink(self):
        """Return a shortlink to the submission.

        For example http://redd.it/eorhm is a shortlink for
        https://www.reddit.com/r/announcements/comments/eorhm/reddit_30_less_typing/.

        """
        return urljoin(self._reddit.config.short_url, self.id)

    def unhide(self):
        """Unhide Submission."""
        self._reddit.post(API_PATH['unhide'], data={'id': self.fullname})


class SubmissionFlair(object):
    """Provide a set of functions pertaining to Submission flair."""

    def __init__(self, submission):
        """Create a SubmissionFlair instance.

        :param submission: The submission associated with the flair functions.

        """
        self.submission = submission

    def choices(self):
        """Return list of available flair choices."""
        url = API_PATH['flairselector'].format(
            subreddit=str(self.submission.subreddit))
        return self.submission._reddit.post(url, data={
            'link': self.submission.fullname})['choices']


class SubmissionModeration(object):
    """Provide a set of functions pertaining to Submission moderation."""

    def __init__(self, submission):
        """Create a SubmissionModeration instance.

        :param submission: The submission to moderate.

        """
        self.submission = submission

    def contest_mode(self, state=True):
        """Set contest mode for the comments of this submission.

        :param state: (boolean) True enables contest mode, False, disables.

        Contest mode have the following effects:
          * The comment thread will default to being sorted randomly.
          * Replies to top-level comments will be hidden behind
            "[show replies]" buttons.
          * Scores will be hidden from non-moderators.
          * Scores accessed through the API (mobile apps, bots) will be
            obscured to "1" for non-moderators.

        """
        self.submission._reddit.post(API_PATH['contest_mode'], data={
            'id': self.submission.fullname, 'state': state})

    def nsfw(self):
        """Mark as not safe for work."""
        self.submission._reddit.post(API_PATH['marknsfw'],
                                     data={'id': self.submission.fullname})

    def sfw(self):
        """Mark as safe for work."""
        self.submission._reddit.post(API_PATH['unmarknsfw'],
                                     data={'id': self.submission.fullname})

    def sticky(self, state=True, bottom=True):
        """Set the submission's sticky state in its subreddit.

        :param state: (boolean) True sets the sticky for the submission, false
            unsets (default: True).
        :param bottom: (boolean) When true, set the submission as the bottom
            sticky. If no top sticky exists, this submission will become the
            top sticky regardless (default: True).

        This submission will replace an existing stickied submission if one
        exists.

        """
        data = {'id': self.submission.fullname, 'state': state}
        if not bottom:
            data['num'] = 1
        return self.submission._reddit.post(API_PATH['sticky_submission'],
                                            data=data)

    def suggested_sort(self, sort='blank'):
        """Set the suggested sort for the comments of the submission.

        :param sort: Can be one of: confidence, top, new, controversial, old,
            random, qa, blank (default: blank).

        """
        self.submission._reddit.post(API_PATH['suggested_sort'], data={
            'id': self.submission.fullname, 'sort': sort})
