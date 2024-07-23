function download-random-jars {
	if [ $# -ne 1 ]; then
    echo "Usage: $0 <target directory>"
    return 1
  fi
	local target_dir=$1

  rate_limit=""
#  rate_limit="--limit-rate=50k"

	wget $rate_limit -P $target_dir -nH --reject="index.html*"  --no-parent https://repo.maven.apache.org/maven2/org/apache/httpcomponents/httpclient/4.5.14/httpclient-4.5.14.jar
	wget $rate_limit -P $target_dir -nH --reject="index.html*"  --no-parent https://repo.maven.apache.org/maven2/org/apache/httpcomponents/fluent-hc/4.5.14/fluent-hc-4.5.14.jar
	wget $rate_limit -P $target_dir -nH --reject="index.html*"  --no-parent https://repo.maven.apache.org/maven2/org/apache/httpcomponents/httpmime/4.5.14/httpmime-4.5.14.jar
	wget $rate_limit -P $target_dir -nH --reject="index.html*"  --no-parent https://repo.maven.apache.org/maven2/org/apache/httpcomponents/httpclient-cache/4.5.14/httpclient-cache-4.5.14.jar
  echo "Downloaded to: $target_dir"
}
