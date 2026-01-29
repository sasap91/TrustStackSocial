#!/bin/bash
# TrustStackSocial VM Creation Script
# Creates a Google Cloud Compute Engine VM instance with appropriate specs

set -e

PROJECT_ID="truststacksocialsp"
INSTANCE_NAME="truststacksocial-vm"
ZONE="us-central1-a"
MACHINE_TYPE="e2-small"
BOOT_DISK_SIZE="20GB"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"
SERVICE_ACCOUNT_NAME="truststacksocial-vm-sa"

echo "=================================="
echo "TrustStackSocial VM Creation"
echo "=================================="
echo ""

# Set the project
echo "Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Check if service account exists, create if not
echo ""
echo "Checking service account..."
if ! gcloud iam service-accounts describe ${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com --project=${PROJECT_ID} &>/dev/null; then
    echo "Creating service account ${SERVICE_ACCOUNT_NAME}..."
    gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} \
        --display-name="TrustStackSocial VM Service Account" \
        --project=${PROJECT_ID}
    
    # Grant Secret Manager access
    echo "Granting Secret Manager access..."
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor"
    
    # Grant Cloud Logging access
    echo "Granting Cloud Logging access..."
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/logging.logWriter"
    
    # Grant Cloud Monitoring access
    echo "Granting Cloud Monitoring access..."
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/monitoring.metricWriter"
else
    echo "Service account already exists."
fi

# Check if instance already exists
echo ""
echo "Checking if VM instance already exists..."
if gcloud compute instances describe ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID} &>/dev/null; then
    echo "VM instance ${INSTANCE_NAME} already exists in zone ${ZONE}."
    echo "Skipping creation. Use 'gcloud compute instances delete ${INSTANCE_NAME} --zone=${ZONE}' to delete it first."
    exit 0
fi

# Create the VM instance
echo ""
echo "Creating VM instance..."
echo "  Name: ${INSTANCE_NAME}"
echo "  Zone: ${ZONE}"
echo "  Machine Type: ${MACHINE_TYPE}"
echo "  Boot Disk: ${BOOT_DISK_SIZE}"
echo "  OS: ${IMAGE_FAMILY}"

gcloud compute instances create ${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --zone=${ZONE} \
    --machine-type=${MACHINE_TYPE} \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --service-account=${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --create-disk=auto-delete=yes,boot=yes,device-name=${INSTANCE_NAME},image=projects/${IMAGE_PROJECT}/global/images/family/${IMAGE_FAMILY},mode=rw,size=${BOOT_DISK_SIZE},type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/pd-standard \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --labels=app=truststacksocial,environment=production \
    --reservation-affinity=any \
    --enable-os-login

echo ""
echo "=================================="
echo "✓ VM instance created successfully!"
echo "=================================="
echo ""
echo "Instance details:"
gcloud compute instances describe ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID} --format="table(name,zone,machineType,status,networkInterfaces[0].accessConfigs[0].natIP)"
echo ""
echo "Next steps:"
echo "1. Wait for the VM to be ready (about 1-2 minutes)"
echo "2. Run: ./deploy/vm-setup.sh to configure the VM"
echo "3. Or SSH into the VM: gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE}"
echo ""


