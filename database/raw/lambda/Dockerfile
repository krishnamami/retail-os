# AWS Lambda Python 3.9 Build Environment
# Purpose: Build psycopg2 binary for exact Lambda runtime compatibility
FROM public.ecr.aws/lambda/python:3.9

RUN yum install -y gcc postgresql-devel python3-devel

WORKDIR /tmp/build
RUN python3.9 -m pip install psycopg2-binary==2.9.9 -t /tmp/build/python/lib/python3.9/site-packages/ --no-cache-dir
RUN mkdir -p /tmp/output && cp -r /tmp/build/python /tmp/output/

RUN /lambda/opt/python/bin/python3.9 -c "import psycopg2; print('SUCCESS: psycopg2 version', psycopg2.__version__)"

CMD ["/bin/bash"]
