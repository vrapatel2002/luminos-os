// FP32 FMA throughput microbenchmark (Vulkan compute).
// Build: gcc -O2 bench.c -lvulkan -o bench     Run: ./bench [name-substring]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <vulkan/vulkan.h>

#define LOCAL   256u
#define GROUPS  65536u
#define THREADS (LOCAL*GROUPS)
#define ITERS   1u
#define FMA_PER 8u
#define RUNS    20

#define VK(x) do{ VkResult r=(x); if(r){ fprintf(stderr,"FAIL %s -> %d\n",#x,r); exit(1);} }while(0)

static double now(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
  return t.tv_sec + t.tv_nsec*1e-9; }

int main(int argc,char**argv){
  const char* want = argc>1 ? argv[1] : "780M";

  VkApplicationInfo ai={VK_STRUCTURE_TYPE_APPLICATION_INFO};
  ai.apiVersion=VK_API_VERSION_1_1; ai.pApplicationName="igpu-bench";
  VkInstanceCreateInfo ici={VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&ai;
  VkInstance inst; VK(vkCreateInstance(&ici,0,&inst));

  uint32_t n=0; VK(vkEnumeratePhysicalDevices(inst,&n,0));
  VkPhysicalDevice*pds=malloc(n*sizeof(*pds)); VK(vkEnumeratePhysicalDevices(inst,&n,pds));
  VkPhysicalDevice pd=VK_NULL_HANDLE; VkPhysicalDeviceProperties props;
  for(uint32_t i=0;i<n;i++){ VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(pds[i],&p);
    fprintf(stderr,"  device %u: %s\n",i,p.deviceName);
    if(strstr(p.deviceName,want)){ pd=pds[i]; props=p; } }
  if(!pd){ fprintf(stderr,"no device matching '%s'\n",want); return 1; }
  printf("device      : %s\n",props.deviceName);
  printf("driver ver  : %u.%u.%u\n",VK_VERSION_MAJOR(props.driverVersion),
         VK_VERSION_MINOR(props.driverVersion),VK_VERSION_PATCH(props.driverVersion));

  uint32_t qn=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,0);
  VkQueueFamilyProperties*qf=malloc(qn*sizeof(*qf));
  vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,qf);
  uint32_t qi=UINT32_MAX;
  for(uint32_t i=0;i<qn;i++) if(qf[i].queueFlags&VK_QUEUE_COMPUTE_BIT){ qi=i; break; }
  if(qi==UINT32_MAX){ fprintf(stderr,"no compute queue\n"); return 1; }

  float prio=1.0f;
  VkDeviceQueueCreateInfo qci={VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
  qci.queueFamilyIndex=qi; qci.queueCount=1; qci.pQueuePriorities=&prio;
  VkDeviceCreateInfo dci={VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
  dci.queueCreateInfoCount=1; dci.pQueueCreateInfos=&qci;
  VkDevice dev; VK(vkCreateDevice(pd,&dci,0,&dev));
  VkQueue q; vkGetDeviceQueue(dev,qi,0,&q);

  VkDeviceSize bytes=(VkDeviceSize)THREADS*16;
  VkBufferCreateInfo bci={VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
  bci.size=bytes; bci.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;
  bci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
  VkBuffer buf; VK(vkCreateBuffer(dev,&bci,0,&buf));
  VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev,buf,&mr);
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd,&mp);
  uint32_t mi=UINT32_MAX;
  for(uint32_t i=0;i<mp.memoryTypeCount;i++){
    if(!(mr.memoryTypeBits&(1u<<i))) continue;
    VkMemoryPropertyFlags f=mp.memoryTypes[i].propertyFlags;
    if((f&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)&&(f&VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)){ mi=i; break; } }
  if(mi==UINT32_MAX){ fprintf(stderr,"no host-visible memory\n"); return 1; }
  VkMemoryAllocateInfo mai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
  mai.allocationSize=mr.size; mai.memoryTypeIndex=mi;
  VkDeviceMemory mem; VK(vkAllocateMemory(dev,&mai,0,&mem));
  VK(vkBindBufferMemory(dev,buf,mem,0));
  void*ptr; VK(vkMapMemory(dev,mem,0,bytes,0,&ptr));
  for(uint32_t i=0;i<THREADS*4;i++) ((float*)ptr)[i]=1.0f;

  FILE*f=fopen("bw.spv","rb"); if(!f){perror("fma.spv");return 1;}
  fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
  uint32_t*code=malloc(sz); if(fread(code,1,sz,f)!=(size_t)sz){return 1;} fclose(f);
  VkShaderModuleCreateInfo smci={VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
  smci.codeSize=sz; smci.pCode=code;
  VkShaderModule sm; VK(vkCreateShaderModule(dev,&smci,0,&sm));

  VkDescriptorSetLayoutBinding b={0,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_COMPUTE_BIT,0};
  VkDescriptorSetLayoutCreateInfo dslci={VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
  dslci.bindingCount=1; dslci.pBindings=&b;
  VkDescriptorSetLayout dsl; VK(vkCreateDescriptorSetLayout(dev,&dslci,0,&dsl));
  VkPushConstantRange pcr={VK_SHADER_STAGE_COMPUTE_BIT,0,4};
  VkPipelineLayoutCreateInfo plci={VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
  plci.setLayoutCount=1; plci.pSetLayouts=&dsl;
  plci.pushConstantRangeCount=1; plci.pPushConstantRanges=&pcr;
  VkPipelineLayout pl; VK(vkCreatePipelineLayout(dev,&plci,0,&pl));
  VkComputePipelineCreateInfo cpci={VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
  cpci.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
  cpci.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT; cpci.stage.module=sm; cpci.stage.pName="main";
  cpci.layout=pl;
  VkPipeline pipe; VK(vkCreateComputePipelines(dev,VK_NULL_HANDLE,1,&cpci,0,&pipe));

  VkDescriptorPoolSize ps={VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1};
  VkDescriptorPoolCreateInfo dpci={VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
  dpci.maxSets=1; dpci.poolSizeCount=1; dpci.pPoolSizes=&ps;
  VkDescriptorPool dp; VK(vkCreateDescriptorPool(dev,&dpci,0,&dp));
  VkDescriptorSetAllocateInfo dsai={VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
  dsai.descriptorPool=dp; dsai.descriptorSetCount=1; dsai.pSetLayouts=&dsl;
  VkDescriptorSet ds; VK(vkAllocateDescriptorSets(dev,&dsai,&ds));
  VkDescriptorBufferInfo dbi={buf,0,bytes};
  VkWriteDescriptorSet w={VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
  w.dstSet=ds; w.dstBinding=0; w.descriptorCount=1;
  w.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; w.pBufferInfo=&dbi;
  vkUpdateDescriptorSets(dev,1,&w,0,0);

  VkCommandPoolCreateInfo cpi={VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
  cpi.queueFamilyIndex=qi;
  VkCommandPool cp; VK(vkCreateCommandPool(dev,&cpi,0,&cp));
  VkCommandBufferAllocateInfo cbai={VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
  cbai.commandPool=cp; cbai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbai.commandBufferCount=1;
  VkCommandBuffer cb; VK(vkAllocateCommandBuffers(dev,&cbai,&cb));
  VkCommandBufferBeginInfo bi={VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
  uint32_t iters=ITERS;
  VK(vkBeginCommandBuffer(cb,&bi));
  vkCmdBindPipeline(cb,VK_PIPELINE_BIND_POINT_COMPUTE,pipe);
  vkCmdBindDescriptorSets(cb,VK_PIPELINE_BIND_POINT_COMPUTE,pl,0,1,&ds,0,0);
  vkCmdPushConstants(cb,pl,VK_SHADER_STAGE_COMPUTE_BIT,0,4,&iters);
  vkCmdDispatch(cb,GROUPS,1,1);
  VK(vkEndCommandBuffer(cb));

  VkSubmitInfo si={VK_STRUCTURE_TYPE_SUBMIT_INFO}; si.commandBufferCount=1; si.pCommandBuffers=&cb;
  VkFenceCreateInfo fci={VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
  VkFence fence; VK(vkCreateFence(dev,&fci,0,&fence));

  double flops_per_run = (double)THREADS*(double)ITERS*(double)FMA_PER*2.0;
  printf("threads     : %u   iters: %u   FMA/thread/iter: %u\n",THREADS,ITERS,FMA_PER);
  printf("GFLOP/run   : %.2f\n",flops_per_run/1e9);

  for(int warm=0;warm<3;warm++){
    VK(vkResetFences(dev,1,&fence));
    VK(vkQueueSubmit(q,1,&si,fence));
    VK(vkWaitForFences(dev,1,&fence,VK_TRUE,UINT64_MAX)); }

  double best=1e9,sum=0;
  for(int r=0;r<RUNS;r++){
    VK(vkResetFences(dev,1,&fence));
    double t0=now();
    VK(vkQueueSubmit(q,1,&si,fence));
    VK(vkWaitForFences(dev,1,&fence,VK_TRUE,UINT64_MAX));
    double dt=now()-t0; sum+=dt; if(dt<best) best=dt; }

  printf("best run    : %.3f ms\n",best*1e3);
  printf("mean run    : %.3f ms\n",(sum/RUNS)*1e3);
  printf("PEAK BW     : %.2f GB/s\n",((double)THREADS*32.0)/best/1e9);
  printf("MEAN BW     : %.2f GB/s\n",((double)THREADS*32.0)/(sum/RUNS)/1e9);
  return 0;
}
