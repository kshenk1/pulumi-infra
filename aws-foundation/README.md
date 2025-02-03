# Pulumi Infra

```
aws ssm send-command \
    --instance-ids "i-00a69b068520d9564" \
    --document-name "AWS-RunShellScript" \
    --parameters commands=whoami \
    --output text \
    --query "Command.CommandId"

aws ssm send-command \
    --instance-ids "i-00a69b068520d9564" \
    --document-name "AWS-RunShellScript" \
    --comment "Installing Java" \
    --parameters commands="yum install -y java-17-amazon-corretto.x86_64 htop" \
    --output text \
    --query "Command.CommandId"

aws ssm send-command \
    --instance-ids "i-00a69b068520d9564" \
    --document-name "AWS-RunShellScript" \
    --comment "Installing Jenkins" \
    --parameters "commands=\
        wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo && \
        rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key && \
        yum install jenkins -y && systemctl daemon-reload && systemctl enable jenkins && systemctl start jenkins && sleep 3 && systemctl status jenkins"
    --output text \
    --query "Command.CommandId"
```