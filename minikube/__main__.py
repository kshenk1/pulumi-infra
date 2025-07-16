import pulumi
import pulumi_kubernetes as kubernetes

app_labels = { "app": "nginx" }
app_name = "nginx"

# Create a deployment
deployment = kubernetes.apps.v1.Deployment(
    app_name,
    spec=kubernetes.apps.v1.DeploymentSpecArgs(
        selector=kubernetes.meta.v1.LabelSelectorArgs(
            match_labels=app_labels
        ),
        replicas=1,
        template=kubernetes.core.v1.PodTemplateSpecArgs(
            metadata=kubernetes.meta.v1.ObjectMetaArgs(
                labels=app_labels
            ),
            spec=kubernetes.core.v1.PodSpecArgs(
                containers=[kubernetes.core.v1.ContainerArgs(
                    name="nginx",
                    image="nginx"
                )]
            )
        )
    )
)

# Create a service
service = kubernetes.core.v1.Service(app_name,
    metadata={
        "labels": deployment.spec["template"]["metadata"]["labels"]
    },
    spec=kubernetes.core.v1.ServiceSpecArgs(
        type="ClusterIP",
        ports=[kubernetes.core.v1.ServicePortArgs(
            port=80,
            protocol="TCP",
            target_port=80,
        )],
        selector=app_labels
    )
)