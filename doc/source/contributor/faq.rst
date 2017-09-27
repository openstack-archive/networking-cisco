Contributor Frequently Asked Questions
======================================

How do I...
-----------

.. _faq_release_note:

...know if a release note is needed for my change?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Reno documentation`_ contains a description of what can be added to each
section of a release note. If, after reading this, you're still unsure about
whether to add a release note for your change or not, keep in mind that it is
intended to contain information for deployers, so changes to unit tests or
documentation are unlikely to require one.

...create a new release note?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By running ``reno`` command via tox, e.g::

  $ tox -e venv -- reno new brief-description-cool-new-release-note
    venv create: /home/foo/networking-cisco/.tox/venv
    venv installdeps: -r/home/foo/networking-cisco/test-requirements.txt
    venv develop-inst: /home/foo/networking-cisco
    venv runtests: PYTHONHASHSEED='0'
    venv runtests: commands[0] | reno new brief-description-cool-new-release-note
    Created new notes file in releasenotes/notes/brief-description-cool-new-release-note-ecb3875dc1cbf6d9.yaml
      venv: commands succeeded
      congratulations :)

  $ git status
    On branch test
    Untracked files:
      (use "git add <file>..." to include in what will be committed)

      releasenotes/notes/brief-description-cool-new-release-note-ecb3875dc1cbf6d9.yaml

Then edit the result file. Note that:

- we prefer to use present tense in release notes. For example, a
  release note should say "Adds support for feature foo", not "Added support
  for feature foo". (We use 'adds' instead of 'add' because grammatically,
  it is "ironic adds support", not "ironic add support".)
- any variant of English spelling (American, British, Canadian, Australian...)
  is acceptable. The release note itself should be consistent and not have
  different spelling variants of the same word.
- Release notes for different plugins should be identified by writing each
  release note in the following format::

    plugin_id: A short summary of the note

    Full release note text explaining the impact of the change.

    https://link-to-launchpad.com/bug-or-rfe-if-there-is-one

To check your release notes you can build the documentation locally by running
the command::

  $ tox -e docs
    Documentation should build out successfully, or errors about the formatting
    should appear.

If successful then you can open your browser and view your release notes
rendered out with the rest by going to::

  file:///<your workspace>/networking-cisco/doc/build/html/reference/releasenotes/index.html

For more information see the `reno documentation`_.

.. _`reno documentation`: https://docs.openstack.org/reno/latest/user/usage.html
