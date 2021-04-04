# python-commons

Run ./setup.sh to set up git pre/post push hook scripts.
Then, a similar script loaded to the environment will execute the pre/post push hook scripts: 
https://stackoverflow.com/a/3812238/1106893

For example loading this script and defining an alias like this will do the trick:
`alias gpwh="git-push-with-hooks.sh"`