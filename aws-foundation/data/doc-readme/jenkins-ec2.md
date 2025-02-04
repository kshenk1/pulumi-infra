# Jenkins EC2
Here we're standing up an Amazon Linux 2023 instance to install jenkins on

This instance will be in a private network, and only accessible via port 8080 (ssh is not open)

You can reach jenkins at https://jenkins.kshenk.net once the following installation has been completed

## Prerequiresites
 * The `foundation` stack must be provisioned prior to this.

## Jenkins installation
```
aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --comment "Installing Java, Jenkins & Docker" \
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