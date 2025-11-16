# RSS Feed Generator

The goal of this project is to generate rss (feed.xml) files from web pages (\*.html) that contain blogs or updates but do not provide a subscribe button or a default RSS feed.

Here is the expected flow and instructions:

1. You will be given an HTML file that needs to be parsed and understood.

2. You will provide a python script that writes a `feed_{}.xml` file that is RSS feed compatible.

3. The `{}` in `feed_{}.xml` will refer to the name of a particular RSS feed.

4. GitHub actions will take care of triggering this periodically, so you don't have to worry about it

5. If you are not given an HTML file that you can parse into an rss feed, either ask for it or explain what the issue with the provided file is.

6. Use existing feeds and parsers as a reference.

7. Update the table in the README.md file with the new feed once you are done
