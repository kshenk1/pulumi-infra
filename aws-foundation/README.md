# Pulumi Infra

```
INSTANCE_ID=""
aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters commands=whoami \
    --output text \
    --query "Command.CommandId"

aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --comment "Installing Jenkins" \
    --parameters commands="yum install -y java-17-amazon-corretto.x86_64 htop docker && \
        wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo && \
        rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key && \
        yum install jenkins -y && \
        usermod -a -G docker jenkins && \
        systemctl daemon-reload && \
        systemctl enable docker && \
        systemctl start docker && \
        systemctl enable jenkins && \
        systemctl start jenkins && sleep 3 && \
        systemctl status jenkins" \
    --output text \
    --query "Command.CommandId"

```