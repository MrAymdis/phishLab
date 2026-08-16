<template>
  <div class="page-container">
    <PageHeader title="发送配置" />

    <!-- 统计概览 -->
    <el-row :gutter="12" style="margin: 16px 16px 0">
      <el-col :span="6" v-for="s in statCards" :key="s.label">
        <div class="card stat-mini" :class="`card-${s.accent}`">
          <div class="stat-title">
            {{ s.label }}<span v-if="s.live" class="live-dot" style="margin-left: 6px" />
          </div>
          <div class="stat-value" :style="s.color ? { color: s.color } : {}">{{ s.value }}</div>
          <div class="stat-sub">{{ s.sub }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="card" style="margin: 16px">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="发送通道" name="channel">
          <div class="toolbar">
            <el-dropdown @command="onAddChannelCommand">
              <el-button type="primary" size="small" :icon="Plus">
                新建通道<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="smtp">SMTP 通道</el-dropdown-item>
                  <el-dropdown-item command="ews">Exchange EWS 通道</el-dropdown-item>
                  <el-dropdown-item command="sms">短信机通道</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-select
              v-model="channelTypeFilter"
              size="small"
              clearable
              placeholder="全部类型"
              style="width: 150px"
            >
              <el-option label="SMTP" value="smtp" />
              <el-option label="Exchange EWS" value="ews" />
              <el-option label="短信机" value="sms" />
            </el-select>
            <el-input
              v-model="channelKw"
              size="small"
              clearable
              placeholder="搜索通道名称 / 服务器 / URL"
              :prefix-icon="Search"
              style="width: 240px"
            />
          </div>
          <el-row v-if="filteredChannels.length" :gutter="12" style="margin-top: 12px">
            <el-col :span="12" v-for="c in filteredChannels" :key="c.id">
              <div class="channel-card card" :class="`card-${c.accent}`">
                <div class="ch-header">
                  <div>
                    <div class="ch-name">{{ c.name }}</div>
                    <el-tag size="small" effect="plain" style="margin-top: 4px">{{ c.type_label }}</el-tag>
                  </div>
                  <el-tag v-if="c.status === 'ok'" type="success" size="small" effect="dark">运行中</el-tag>
                  <el-tag v-else type="danger" size="small" effect="dark">异常</el-tag>
                </div>
                <div class="ch-meta" v-if="c.type === 'smtp'">
                  <span>服务器</span><code>{{ c.server }}:{{ c.port }}</code>
                  <el-tag size="small" :type="c.ssl ? 'success' : 'info'">{{ c.ssl ? 'SSL/TLS' : 'STARTTLS' }}</el-tag>
                </div>
                <div class="ch-meta" v-else-if="c.type === 'ews'">
                  <span>服务URL</span><code>{{ c.url }}</code>
                  <el-tag size="small" effect="plain">{{ c.auth_mode }}</el-tag>
                </div>
                <div class="ch-meta" v-else-if="c.type === 'sms'">
                  <span>服务商</span><code>{{ c.provider }}</code>
                  <el-tag size="small" effect="plain">签名：{{ c.signature }}</el-tag>
                </div>
                <div class="ch-score">
                  <span class="ch-score-label">送达评分</span>
                  <el-progress
                    :percentage="c.score"
                    :stroke-width="10"
                    :color="scoreColor(c.score)"
                    :format="(v: number) => `${v} 分`"
                    style="flex: 1; margin-left: 12px"
                  />
                </div>
                <div class="ch-footer">
                  <span class="ch-test-time">最近测试：{{ c.last_test }}</span>
                  <div>
                    <el-button size="small" link @click="openChannelDialog(c.type, c)">编辑</el-button>
                    <el-button
                      size="small"
                      link
                      type="primary"
                      :loading="testingChannelId === c.id"
                      @click="testChannel(c)"
                    >连通测试</el-button>
                    <el-button size="small" link type="danger" @click="deleteChannel(c)">删除</el-button>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>
          <el-empty v-else description="没有匹配的通道，请调整筛选条件" style="margin-top: 12px" />
        </el-tab-pane>

        <el-tab-pane label="伪装发件人" name="sender">
          <div class="toolbar">
            <el-button type="primary" size="small" :icon="Plus" @click="senderDialog = true">新增伪装发件人</el-button>
          </div>
          <el-table :data="senderRows" size="small" style="margin-top: 12px">
            <el-table-column label="显示名" prop="display_name" width="140" />
            <el-table-column label="发件地址" width="200">
              <template #default="{ row }">
                <code>{{ row.address }}</code>
              </template>
            </el-table-column>
            <el-table-column label="Reply-To" width="200">
              <template #default="{ row }">
                <code v-if="row.reply_to">{{ row.reply_to }}</code>
                <span v-else style="color: var(--color-text-tertiary)">—</span>
              </template>
            </el-table-column>
            <el-table-column label="场景标签" min-width="200">
              <template #default="{ row }">
                <el-tag v-for="t in row.scene_tags" :key="t" size="small" effect="plain" style="margin-right: 4px">
                  {{ t }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关联通道" prop="channel" width="160" />
            <el-table-column label="操作" width="200">
              <template #default>
                <el-button size="small" link>编辑</el-button>
                <el-button size="small" link type="primary">测试</el-button>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="域名与DNS" name="domain">
          <div class="toolbar">
            <el-button type="primary" size="small" :icon="Plus" @click="openDomainDialog">新增域名</el-button>
          </div>
          <el-table :data="domainRows" size="small" style="margin-top: 12px">
            <el-table-column prop="domain" label="域名" min-width="220">
              <template #default="{ row }">
                <code>{{ row.domain }}</code>
              </template>
            </el-table-column>
            <el-table-column label="SPF" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="dnsTagType(row.spf)" size="small" effect="dark">{{ row.spf }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="DKIM" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="dnsTagType(row.dkim)" size="small" effect="dark">{{ row.dkim }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="DMARC" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="dnsTagType(row.dmarc)" size="small" effect="dark">{{ row.dmarc }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="送达评分" width="180">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.score"
                  :stroke-width="10"
                  :color="scoreColor(row.score)"
                  :format="(v: number) => `${v} 分`"
                />
              </template>
            </el-table-column>
            <el-table-column prop="last_check" label="最近检测" width="160" />
            <el-table-column label="操作" width="220">
              <template #default>
                <el-button size="small" link type="primary">立即检测</el-button>
                <el-button size="small" link>修复指引</el-button>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="score-legend">
            <el-tag size="small" type="success" effect="dark">≥ 98 绿色</el-tag>
            <span>优秀：几乎全部到达收件箱</span>
            <el-tag size="small" type="warning" effect="dark">90 ~ 97 黄色</el-tag>
            <span>良好：少量进入垃圾箱</span>
            <el-tag size="small" type="danger" effect="dark">{'< 90 红色'}</el-tag>
            <span>较差：大量被拦截/进垃圾箱</span>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 新建/编辑发送通道弹窗（SMTP / Exchange EWS / 短信机 动态表单） -->
    <el-dialog
      v-model="channelDialogVisible"
      :title="editingChannel ? '编辑通道' : '新建通道'"
      width="680px"
    >
      <el-form
        ref="channelFormRef"
        :model="channelForm"
        :rules="channelRules"
        label-width="130px"
        size="default"
        class="channel-form"
      >
        <el-form-item label="通道名称" prop="name">
          <el-input v-model="channelForm.name" placeholder="如：平台默认SMTP" />
        </el-form-item>
        <el-form-item label="通道类型" required>
          <div class="type-cards">
            <div
              v-for="t in CHANNEL_TYPES"
              :key="t.value"
              class="type-card"
              :class="{ selected: channelForm.type === t.value }"
              @click="channelForm.type = t.value"
            >
              <div class="type-card-title">{{ t.label }}</div>
              <div class="type-card-desc">{{ t.desc }}</div>
            </div>
          </div>
        </el-form-item>

        <!-- SMTP 字段 -->
        <template v-if="channelForm.type === 'smtp'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="SMTP服务器地址" prop="smtp_host">
                <el-input v-model="channelForm.smtp_host" placeholder="如：smtp.phish-platform.com" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="端口" prop="smtp_port">
                <el-input v-model="channelForm.smtp_port" placeholder="如：587" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="加密方式">
            <el-select v-model="channelForm.smtp_encryption" style="width: 100%">
              <el-option label="STARTTLS（推荐）" value="STARTTLS" />
              <el-option label="SSL/TLS" value="SSL" />
              <el-option label="无加密（不推荐）" value="NONE" />
            </el-select>
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="发送账号" prop="smtp_user">
                <el-input v-model="channelForm.smtp_user" placeholder="如：noreply@company.com" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="密码 / 授权码" prop="smtp_pass">
                <el-input
                  v-model="channelForm.smtp_pass"
                  type="password"
                  show-password
                  placeholder="输入SMTP密码或授权码"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <!-- Exchange EWS 字段 -->
        <template v-else-if="channelForm.type === 'ews'">
          <el-form-item label="EWS服务URL" prop="ews_url">
            <el-input v-model="channelForm.ews_url" placeholder="https://outlook.office365.com/EWS/Exchange.asmx" />
            <div class="form-hint">Office365默认：https://outlook.office365.com/EWS/Exchange.asmx</div>
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="认证账号" prop="ews_user">
                <el-input v-model="channelForm.ews_user" placeholder="如：noreply@company.onmicrosoft.com" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="密码" prop="ews_pass">
                <el-input
                  v-model="channelForm.ews_pass"
                  type="password"
                  show-password
                  placeholder="输入Exchange账号密码"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="认证模式">
            <el-select v-model="channelForm.ews_auth_mode" style="width: 100%">
              <el-option label="基本认证（Basic Auth）" value="basic" />
              <el-option label="OAuth 2.0（现代认证）" value="oauth" />
            </el-select>
            <div class="form-hint">Office365建议使用OAuth 2.0，需在Azure AD注册应用</div>
          </el-form-item>
          <template v-if="channelForm.ews_auth_mode === 'oauth'">
            <el-alert
              type="info"
              :closable="false"
              show-icon
              title="需在Azure AD注册应用"
              description="请在 Azure AD 管理中心注册应用并授予 EWS 访问权限，获取以下三项凭据后填入。"
              style="margin-bottom: 18px"
            />
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="Client ID" prop="ews_client_id">
                  <el-input v-model="channelForm.ews_client_id" placeholder="Azure AD应用的Client ID" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Client Secret" prop="ews_client_secret">
                  <el-input
                    v-model="channelForm.ews_client_secret"
                    type="password"
                    show-password
                    placeholder="Azure AD应用的Client Secret"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="Tenant ID">
              <el-input v-model="channelForm.ews_tenant_id" placeholder="如：company.onmicrosoft.com" />
            </el-form-item>
          </template>
        </template>

        <!-- 短信机 SMS 字段 -->
        <template v-else>
          <el-form-item label="短信通道类型">
            <el-select v-model="channelForm.sms_provider" style="width: 100%">
              <el-option label="阿里云短信服务" value="aliyun" />
              <el-option label="腾讯云短信" value="tencent" />
              <el-option label="华为云短信" value="huawei" />
              <el-option label="网易云信" value="netease" />
              <el-option label="自定义HTTP网关" value="custom" />
              <el-option label="4G短信模块（串口/AT指令）" value="4g" />
            </el-select>
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item
                :label="channelForm.sms_provider === '4g' ? '管理IP' : 'API地址 / 网关URL'"
                prop="sms_url"
              >
                <el-input
                  v-model="channelForm.sms_url"
                  :placeholder="
                    channelForm.sms_provider === '4g'
                      ? '如：http://192.168.1.100'
                      : '如：https://dysmsapi.aliyuncs.com'
                  "
                />
                <div class="form-hint">
                  {{
                    channelForm.sms_provider === '4g'
                      ? '4G短信模块的管理地址'
                      : '4G模块填写管理IP，如：http://192.168.1.100'
                  }}
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="短信签名" prop="sms_signature">
                <el-input v-model="channelForm.sms_signature" placeholder="如：【企业安全中心】" />
                <div class="form-hint">短信开头显示的签名名称</div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="API Key" prop="sms_api_key">
                <el-input v-model="channelForm.sms_api_key" placeholder="如：LTAI5tXXXXXXXX（AccessKey）" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="API Secret" prop="sms_api_secret">
                <el-input
                  v-model="channelForm.sms_api_secret"
                  type="password"
                  show-password
                  placeholder="输入API密钥（AccessSecret）"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <template v-if="channelForm.sms_provider === '4g'">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="串口设备">
                  <el-input v-model="channelForm.sms_port_dev" placeholder="如：/dev/ttyUSB0 或 COM3" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="波特率">
                  <el-select v-model="channelForm.sms_baudrate" style="width: 100%">
                    <el-option label="9600" value="9600" />
                    <el-option label="115200" value="115200" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="SIM卡号码">
              <el-input v-model="channelForm.sms_sim" placeholder="如：1069001234567" />
            </el-form-item>
          </template>
          <el-form-item label="短信模板ID">
            <el-input v-model="channelForm.sms_template_id" placeholder="如：SMS_123456789（留空则使用默认模板）" />
            <div class="form-hint">在短信服务商后台申请的模板编号</div>
          </el-form-item>
        </template>

        <!-- 伪装发件人配置 -->
        <div class="sender-block">
          <div class="sender-block-title">伪装发件人配置</div>
          <el-form-item label="发件人显示名称" prop="sender_display_name">
            <el-input v-model="channelForm.sender_display_name" placeholder="如：财务部-报销系统通知" />
            <div class="form-hint">员工收到邮件/短信时显示的发件人名称</div>
          </el-form-item>
          <template v-if="channelForm.type !== 'sms'">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="发件邮箱地址" prop="sender_email">
                  <el-input v-model="channelForm.sender_email" placeholder="如：noreply@finance-company-notice.com" />
                  <div class="form-hint">邮件演练专用，需使用已配置的域名</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="回复地址 Reply-To">
                  <el-input v-model="channelForm.sender_reply_to" placeholder="默认同发件邮箱" />
                  <div class="form-hint">建议设为不可回复地址</div>
                </el-form-item>
              </el-col>
            </el-row>
          </template>
          <template v-else>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="短信发送号码" prop="sender_sms_number">
                  <el-input v-model="channelForm.sender_sms_number" placeholder="如：1069001234567" />
                  <div class="form-hint">短信通道的发送号码或扩展号</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="短信签名" prop="sender_sms_sign">
                  <el-input v-model="channelForm.sender_sms_sign" placeholder="如：【企业安全中心】" />
                  <div class="form-hint">短信正文前缀签名</div>
                </el-form-item>
              </el-col>
            </el-row>
          </template>
          <el-form-item label="适用场景标签">
            <el-checkbox-group v-model="channelForm.sender_tags">
              <el-checkbox v-for="t in SCENE_TAGS" :key="t" :value="t">{{ t }}</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </div>

        <el-form-item label="每日发送上限">
          <el-input v-model="channelForm.daily_limit" placeholder="如：5000" style="width: 220px" />
          <div class="form-hint">超出上限将自动顺延至次日发送</div>
        </el-form-item>
        <el-form-item label="设为默认服务器">
          <el-switch v-model="channelForm.is_default" />
          <span class="switch-note">开启后，新建演练默认使用此服务器</span>
        </el-form-item>

        <!-- 测试邮件发送：SMTP 通道新增/编辑均可直接测试 -->
        <template v-if="channelForm.type === 'smtp'">
          <el-divider content-position="left">测试邮件发送</el-divider>
          <el-form-item label="收件邮箱">
            <div class="test-email-row">
              <el-input
                v-model="testEmailTo"
                placeholder="如：zhangsan@company.com"
                style="width: 260px"
                clearable
              />
              <el-button
                type="primary"
                plain
                :icon="Promotion"
                :loading="testEmailLoading"
                @click="sendTestEmail"
              >发送测试邮件</el-button>
            </div>
            <el-alert
              v-if="testEmailResult"
              :type="testEmailResult.ok ? 'success' : 'error'"
              :closable="false"
              show-icon
              style="margin-top: 8px; width: 100%"
            >
              <template #title>{{ testEmailResult.message }}</template>
            </el-alert>
            <div class="form-hint">
              按弹窗当前配置真实发送一封测试邮件；新增通道可先测后存，已保存通道会同步刷新「最近测试」记录
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="channelDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitChannelForm">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- 添加演练域名弹窗 -->
    <el-dialog v-model="domainDialogVisible" title="添加演练域名" width="560px">
      <el-form
        ref="domainFormRef"
        :model="domainForm"
        :rules="domainRules"
        label-width="110px"
        size="default"
      >
        <el-form-item label="域名" prop="domain">
          <el-input v-model="domainForm.domain" placeholder="如：finance-company-notice.com" />
          <div class="form-hint">建议使用与真实域名相似但有差异的域名，避免被网关拦截</div>
        </el-form-item>
        <el-form-item label="用途说明">
          <el-input v-model="domainForm.purpose" placeholder="如：财务报销场景专用" />
        </el-form-item>
        <el-form-item label="DNS记录配置指引">
          <div class="dns-guide">
            <div class="dns-guide-title">添加域名后，请在域名DNS管理面板中配置以下3条记录：</div>
            <div class="dns-record">
              <span class="dns-record-type">SPF (TXT)</span> → v=spf1 include:phish-platform.com ~all
            </div>
            <div class="dns-record">
              <span class="dns-record-type">DKIM (TXT)</span> → 系统自动生成公钥
            </div>
            <div class="dns-record">
              <span class="dns-record-type">DMARC (TXT)</span> → v=DMARC1; p=none; rua=mailto:admin@company.com
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="domainDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDomainForm">添加并生成DNS记录</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="senderDialog" title="新增伪装发件人" width="520px">
      <el-form :model="senderForm" label-width="100px" size="default">
        <el-form-item label="显示名">
          <el-input v-model="senderForm.display_name" placeholder="财务部通知" />
        </el-form-item>
        <el-form-item label="发件地址">
          <el-input v-model="senderForm.address" placeholder="finance@phish-mail.company.com" />
        </el-form-item>
        <el-form-item label="Reply-To">
          <el-input v-model="senderForm.reply_to" placeholder="可选，回复接收地址" />
        </el-form-item>
        <el-form-item label="场景标签">
          <el-select v-model="senderForm.scene_tags" multiple collapse-tags style="width: 100%">
            <el-option label="财务报销" value="财务报销" />
            <el-option label="HR通知" value="HR通知" />
            <el-option label="系统升级" value="系统升级" />
            <el-option label="中奖通知" value="中奖通知" />
            <el-option label="节假日" value="节假日" />
            <el-option label="安全类" value="安全类" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联通道">
          <el-select v-model="senderForm.channel" style="width: 100%">
            <el-option label="主SMTP (smtp.company.com)" value="主SMTP" />
            <el-option label="备用SMTP (smtp2.company.com)" value="备用SMTP" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="senderDialog = false">取消</el-button>
        <el-button type="primary" @click="saveSender">确认添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { Plus, ArrowDown, Search, Promotion } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import PageHeader from '@/components/base/PageHeader.vue'
import { channelApi } from '@/api'

type ChannelType = 'smtp' | 'ews' | 'sms'

interface ChannelItem {
  id: number
  name: string
  type: ChannelType
  type_label: string
  accent: string
  status: 'ok' | 'error'
  score: number
  last_test: string
  server?: string
  port?: number
  ssl?: boolean
  url?: string
  auth_mode?: string
  provider?: string
  signature?: string
}

const activeTab = ref('channel')

function scoreColor(score: number) {
  if (score >= 98) return '#67c23a'
  if (score >= 90) return '#e6a23c'
  return '#f56c6c'
}
function dnsTagType(v: string) {
  if (v === 'OK') return 'success'
  if (v === 'WARN') return 'warning'
  return 'danger'
}

const channels = ref<ChannelItem[]>([
  { id: 1, name: '主SMTP通道', type: 'smtp', type_label: 'SMTP', accent: 'blue', status: 'ok',
    server: 'smtp.company.com', port: 465, ssl: true, score: 96, last_test: '2026-08-15 10:22' },
  { id: 2, name: '备用SMTP通道', type: 'smtp', type_label: 'SMTP', accent: 'teal', status: 'ok',
    server: 'smtp2.company.com', port: 587, ssl: false, score: 92, last_test: '2026-08-14 18:05' },
  { id: 3, name: 'Exchange EWS (Office365)', type: 'ews', type_label: 'Exchange EWS', accent: 'purple', status: 'ok',
    url: 'https://outlook.office365.com/EWS/Exchange.asmx', auth_mode: 'OAuth2 · Azure AD', score: 98, last_test: '2026-08-15 09:40' },
  { id: 4, name: '阿里云短信', type: 'sms', type_label: '短信机', accent: 'orange', status: 'ok',
    provider: '阿里云 Dysmsapi', signature: '【安全演练】', score: 88, last_test: '2026-08-13 15:30' },
  { id: 5, name: '腾讯云短信', type: 'sms', type_label: '短信机', accent: 'green', status: 'error',
    provider: '腾讯云 SMS', signature: '【公司通知】', score: 0, last_test: '2026-08-10 失败' },
  { id: 6, name: '自定义 HTTP 短信网关', type: 'sms', type_label: '短信机', accent: 'red', status: 'ok',
    provider: '自定义 HTTP Webhook', signature: '【系统公告】', score: 82, last_test: '2026-08-12 11:15' },
])

// ========== 统计卡片（由当前通道 mock 数据计算） ==========
const statCards = computed(() => {
  const okCount = channels.value.filter((c) => c.status === 'ok').length
  return [
    { label: '服务器总数', value: channels.value.length, sub: 'SMTP / EWS / 短信机 三类通道', accent: 'blue', color: '', live: false },
    { label: '正常可用', value: okCount, sub: '运行中，可随时发送', accent: 'green', color: 'var(--color-text-success)', live: true },
    { label: '异常需关注', value: channels.value.length - okCount, sub: '请及时检查连接配置', accent: 'orange', color: 'var(--accent-orange)', live: false },
    { label: '本月发送总量', value: '12,860', sub: '日均约 415 封', accent: 'teal', color: '', live: false },
  ]
})

// ========== 通道列表：客户端筛选 ==========
const channelKw = ref('')
const channelTypeFilter = ref('')
const filteredChannels = computed(() => {
  const kw = channelKw.value.trim().toLowerCase()
  return channels.value.filter((c) => {
    if (channelTypeFilter.value && c.type !== channelTypeFilter.value) return false
    if (!kw) return true
    const haystack = [c.name, c.server ?? '', c.url ?? '', c.provider ?? '', c.signature ?? '']
      .join(' ')
      .toLowerCase()
    return haystack.includes(kw)
  })
})

// ========== 新建/编辑通道弹窗 ==========
const CHANNEL_TYPES: { value: ChannelType; label: string; desc: string }[] = [
  { value: 'smtp', label: 'SMTP', desc: '标准邮件发送协议' },
  { value: 'ews', label: 'Exchange (EWS)', desc: 'Office365 / 本地Exchange' },
  { value: 'sms', label: '短信机 (SMS)', desc: '短信网关API / 4G模块' },
]
const SCENE_TAGS = ['财务类', 'HR类', '系统类', '节假日', '中奖类', '安全类']

interface ChannelFormState {
  name: string
  type: ChannelType
  // SMTP
  smtp_host: string
  smtp_port: string
  smtp_encryption: 'STARTTLS' | 'SSL' | 'NONE'
  smtp_user: string
  smtp_pass: string
  // Exchange EWS
  ews_url: string
  ews_user: string
  ews_pass: string
  ews_auth_mode: 'basic' | 'oauth'
  ews_client_id: string
  ews_client_secret: string
  ews_tenant_id: string
  // 短信机 SMS
  sms_provider: string
  sms_url: string
  sms_signature: string
  sms_api_key: string
  sms_api_secret: string
  sms_template_id: string
  sms_port_dev: string
  sms_baudrate: string
  sms_sim: string
  // 公共字段
  daily_limit: string
  is_default: boolean
  // 伪装发件人
  sender_display_name: string
  sender_email: string
  sender_reply_to: string
  sender_sms_number: string
  sender_sms_sign: string
  sender_tags: string[]
}

function defaultChannelForm(type: ChannelType): ChannelFormState {
  return {
    name: '', type,
    smtp_host: '', smtp_port: '587', smtp_encryption: 'STARTTLS', smtp_user: '', smtp_pass: '',
    ews_url: '', ews_user: '', ews_pass: '', ews_auth_mode: 'basic',
    ews_client_id: '', ews_client_secret: '', ews_tenant_id: '',
    sms_provider: 'aliyun', sms_url: '', sms_signature: '', sms_api_key: '', sms_api_secret: '',
    sms_template_id: '', sms_port_dev: '', sms_baudrate: '115200', sms_sim: '',
    daily_limit: '5000', is_default: false,
    sender_display_name: '', sender_email: '', sender_reply_to: '',
    sender_sms_number: '', sender_sms_sign: '', sender_tags: [],
  }
}

const channelDialogVisible = ref(false)
const editingChannel = ref<ChannelItem | null>(null)
const channelFormRef = ref<FormInstance>()
const channelForm = reactive<ChannelFormState>(defaultChannelForm('smtp'))

const channelRules = computed<FormRules>(() => {
  const req = (message: string, trigger: 'blur' | 'change' = 'blur') => ({ required: true, message, trigger })
  const rules: FormRules = {
    name: [req('请输入通道名称')],
    sender_display_name: [req('请输入发件人显示名称')],
  }
  if (channelForm.type === 'smtp') {
    rules.smtp_host = [req('请输入SMTP服务器地址')]
    rules.smtp_port = [req('请输入端口')]
    rules.smtp_user = [req('请输入发送账号')]
    rules.smtp_pass = [req('请输入密码 / 授权码')]
  } else if (channelForm.type === 'ews') {
    rules.ews_url = [req('请输入EWS服务URL')]
    rules.ews_user = [req('请输入认证账号')]
    rules.ews_pass = [req('请输入密码')]
    if (channelForm.ews_auth_mode === 'oauth') {
      rules.ews_client_id = [req('请输入Client ID')]
      rules.ews_client_secret = [req('请输入Client Secret')]
    }
  } else {
    rules.sms_url = [req(channelForm.sms_provider === '4g' ? '请输入管理IP' : '请输入API地址 / 网关URL')]
    rules.sms_signature = [req('请输入短信签名')]
    rules.sms_api_key = [req('请输入API Key')]
    rules.sms_api_secret = [req('请输入API Secret')]
  }
  if (channelForm.type === 'sms') {
    rules.sender_sms_number = [req('请输入短信发送号码')]
    rules.sender_sms_sign = [req('请输入短信签名')]
  } else {
    rules.sender_email = [
      req('请输入发件邮箱地址'),
      { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] },
    ]
  }
  return rules
})

function onAddChannelCommand(command: string | number | object) {
  openChannelDialog(String(command) as ChannelType)
}

function guessSmsProvider(provider?: string): string {
  if (!provider) return 'aliyun'
  if (provider.includes('阿里')) return 'aliyun'
  if (provider.includes('腾讯')) return 'tencent'
  if (provider.includes('华为')) return 'huawei'
  if (provider.includes('网易')) return 'netease'
  if (provider.includes('自定义')) return 'custom'
  return 'aliyun'
}

function openChannelDialog(type: ChannelType, channel?: ChannelItem) {
  editingChannel.value = channel ?? null
  // 重置测试邮件状态
  testEmailTo.value = ''
  testEmailResult.value = null
  Object.assign(channelForm, defaultChannelForm(type))
  if (channel) {
    channelForm.name = channel.name
    if (channel.type === 'smtp') {
      channelForm.smtp_host = channel.server ?? ''
      channelForm.smtp_port = channel.port ? String(channel.port) : '587'
      channelForm.smtp_encryption = channel.ssl ? 'SSL' : 'STARTTLS'
    } else if (channel.type === 'ews') {
      channelForm.ews_url = channel.url ?? ''
      channelForm.ews_auth_mode = channel.auth_mode?.includes('OAuth') ? 'oauth' : 'basic'
    } else {
      channelForm.sms_provider = guessSmsProvider(channel.provider)
      channelForm.sms_signature = channel.signature ?? ''
    }
  }
  channelDialogVisible.value = true
  nextTick(() => channelFormRef.value?.clearValidate())
}

/** 弹窗表单 → ChannelCreate payload（config 键与后端 channel.service.create_channel 对齐） */
function buildChannelPayload(): Record<string, unknown> {
  let config: Record<string, unknown>
  if (channelForm.type === 'smtp') {
    config = {
      smtp_host: channelForm.smtp_host,
      smtp_port: channelForm.smtp_port,
      smtp_encryption: channelForm.smtp_encryption,
      smtp_user: channelForm.smtp_user,
      smtp_pass: channelForm.smtp_pass,
    }
  } else if (channelForm.type === 'ews') {
    config = {
      ews_url: channelForm.ews_url,
      ews_user: channelForm.ews_user,
      ews_pass: channelForm.ews_pass,
      ews_auth_mode: channelForm.ews_auth_mode,
      ews_client_id: channelForm.ews_client_id,
      ews_client_secret: channelForm.ews_client_secret,
      ews_tenant_id: channelForm.ews_tenant_id,
    }
  } else {
    config = {
      sms_provider: channelForm.sms_provider,
      sms_url: channelForm.sms_url,
      sms_signature: channelForm.sms_signature,
      sms_api_key: channelForm.sms_api_key,
      sms_api_secret: channelForm.sms_api_secret,
      sms_template_id: channelForm.sms_template_id,
      sms_port_dev: channelForm.sms_port_dev,
      sms_baudrate: channelForm.sms_baudrate,
      sms_sim: channelForm.sms_sim,
    }
  }
  return {
    name: channelForm.name,
    type: channelForm.type,
    daily_limit: Number(channelForm.daily_limit) || 5000,
    is_default: channelForm.is_default,
    config,
    // TODO: 弹窗内「伪装发件人配置」需单独走 sender-profiles 接口，暂不同时提交
  }
}

async function submitChannelForm() {
  const formEl = channelFormRef.value
  if (!formEl) return
  const valid = await formEl.validate().catch(() => false)
  if (!valid) return
  try {
    if (editingChannel.value) {
      await channelApi.updateChannel(editingChannel.value.id, buildChannelPayload())
      ElMessage.success('通道配置已更新')
    } else {
      await channelApi.createChannel(buildChannelPayload())
      ElMessage.success('发送通道已创建')
    }
    await loadChannels()
    channelDialogVisible.value = false
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// ========== 添加域名弹窗 ==========
const domainDialogVisible = ref(false)
const domainFormRef = ref<FormInstance>()
const domainForm = reactive({ domain: '', purpose: '' })
const domainRules: FormRules = {
  domain: [
    { required: true, message: '请输入域名', trigger: 'blur' },
    {
      pattern: /^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/,
      message: '请输入正确的域名格式',
      trigger: 'blur',
    },
  ],
}

function openDomainDialog() {
  domainForm.domain = ''
  domainForm.purpose = ''
  domainDialogVisible.value = true
  nextTick(() => domainFormRef.value?.clearValidate())
}

async function submitDomainForm() {
  const formEl = domainFormRef.value
  if (!formEl) return
  const valid = await formEl.validate().catch(() => false)
  if (!valid) return
  try {
    await channelApi.createDomain({ domain: domainForm.domain, purpose: domainForm.purpose })
    await loadDomains()
    ElMessage.success('域名已添加，DNS记录已生成，请前往域名DNS面板配置')
    domainDialogVisible.value = false
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// ========== 伪装发件人（独立 Tab 弹窗，保留原实现） ==========
const senderDialog = ref(false)
const senderForm = reactive({
  display_name: '', address: '', reply_to: '', scene_tags: [] as string[], channel: '',
})

async function saveSender() {
  if (!senderForm.display_name || !senderForm.address) {
    ElMessage.warning('请填写显示名和发件地址')
    return
  }
  try {
    await channelApi.createSenderProfile({
      name: senderForm.display_name,
      channel_type: 'mail',
      display_name: senderForm.display_name,
      from_addr: senderForm.address,
      reply_to: senderForm.reply_to,
      scene_tags: senderForm.scene_tags,
      // TODO: 关联通道(channel) 后端 SenderProfileCreate 暂未支持，默认走默认通道
    })
    await loadSenderProfiles()
    senderDialog.value = false
    ElMessage.success('伪装发件人已添加')
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

interface SenderRow {
  id: number
  display_name: string
  address: string
  reply_to: string
  scene_tags: string[]
  channel: string
}

interface DomainRow {
  id: number
  domain: string
  spf: string
  dkim: string
  dmarc: string
  score: number
  last_check: string
}

const senderRows = ref<SenderRow[]>([
  { id: 1, display_name: '财务部通知', address: 'finance-noreply@phish-mail.company.com', reply_to: '', scene_tags: ['财务报销'], channel: '主SMTP' },
  { id: 2, display_name: 'IT运维中心', address: 'it-support@phish-mail.company.com', reply_to: 'helpdesk@company.com', scene_tags: ['系统升级', '中奖通知'], channel: '主SMTP' },
  { id: 3, display_name: '人力资源部', address: 'hr@phish-mail.company.com', reply_to: '', scene_tags: ['HR通知', '节假日'], channel: 'Exchange EWS' },
  { id: 4, display_name: '员工福利委员会', address: 'welfare@phish-mail.company.com', reply_to: '', scene_tags: ['中奖通知', '节假日'], channel: '备用SMTP' },
  { id: 5, display_name: '安全中心', address: 'security@phish-mail.company.com', reply_to: '', scene_tags: ['系统升级'], channel: '主SMTP' },
])

const domainRows = ref<DomainRow[]>([
  { id: 1, domain: 'phish-mail.company.com', spf: 'OK', dkim: 'OK', dmarc: 'OK', score: 99, last_check: '2026-08-15 03:00' },
  { id: 2, domain: 'company-security.info', spf: 'OK', dkim: 'WARN', dmarc: 'OK', score: 93, last_check: '2026-08-15 03:00' },
  { id: 3, domain: 'hr-notice.work', spf: 'OK', dkim: 'FAIL', dmarc: 'WARN', score: 85, last_check: '2026-08-15 03:00' },
  { id: 4, domain: 'it-alert.top', spf: 'FAIL', dkim: 'FAIL', dmarc: 'FAIL', score: 62, last_check: '2026-08-14 03:00' },
])

// ============ 接口加载（失败时保留演示数据） ============
async function loadChannels() {
  try {
    const list = (await channelApi.list()) as ChannelItem[]
    if (Array.isArray(list)) channels.value = list
  } catch {
    // 失败提示由 http 拦截器统一弹出；保留已有数据不覆盖
  }
}

/** 连通测试：调用后端 TCP 探测，刷新卡片上的评分/最近测试时间 */
const testingChannelId = ref<number | null>(null)

async function testChannel(c: ChannelItem) {
  testingChannelId.value = c.id
  try {
    const result = await channelApi.test(c.id)
    if (result.ok) {
      ElMessage.success(`「${c.name}」连通性正常 · 送达评分 ${result.score} 分 · 延迟 ${result.latency_ms ?? '-'}ms`)
    } else {
      ElMessage.error(`「${c.name}」连通失败：${result.message}`)
    }
    await loadChannels()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    testingChannelId.value = null
  }
}

/** 删除通道：二次确认后调用后端删除并刷新列表 */
async function deleteChannel(c: ChannelItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除发送通道「${c.name}」？历史演练仅保留通道 ID 引用，不影响既有报表。`,
      '删除通道',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return // 用户取消
  }
  try {
    await channelApi.deleteChannel(c.id)
    ElMessage.success(`通道「${c.name}」已删除`)
    await loadChannels()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// ============ 测试邮件发送 ============
const testEmailTo = ref('')
const testEmailLoading = ref(false)
const testEmailResult = ref<{ ok: boolean; message: string } | null>(null)

async function sendTestEmail() {
  const to = testEmailTo.value.trim()
  if (!to || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) {
    ElMessage.warning('请填写正确的收件邮箱地址')
    return
  }
  testEmailLoading.value = true
  testEmailResult.value = null
  try {
    let result
    if (editingChannel.value) {
      // 已保存通道：按通道 ID 发信并回写最近测试
      result = await channelApi.sendTestEmail(editingChannel.value.id, to)
      if (result.ok) await loadChannels()
    } else {
      // 新增通道：用弹窗当前配置发信（不落库）
      result = await channelApi.sendTestEmailDraft({
        to,
        name: channelForm.name || '未保存的通道',
        type: channelForm.type,
        config: buildChannelPayload().config,
      })
    }
    testEmailResult.value = { ok: result.ok, message: result.message }
    if (result.ok) ElMessage.success('测试邮件已发送')
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    testEmailLoading.value = false
  }
}

async function loadSenderProfiles() {
  try {
    const list = (await channelApi.senderProfiles()) as SenderRow[]
    if (Array.isArray(list)) senderRows.value = list
  } catch {
    // 失败提示由 http 拦截器统一弹出；保留已有数据不覆盖
  }
}

async function loadDomains() {
  try {
    const list = (await channelApi.domains()) as DomainRow[]
    if (Array.isArray(list)) domainRows.value = list
  } catch {
    // 失败提示由 http 拦截器统一弹出；保留已有数据不覆盖
  }
}

onMounted(() => {
  loadChannels()
  loadSenderProfiles()
  loadDomains()
})
</script>

<style scoped lang="scss">
.stat-mini {
  .stat-title {
    font-size: 12px;
    color: var(--color-text-secondary);
    display: flex;
    align-items: center;
  }
  .stat-value { font-size: 24px; font-weight: 600; margin-top: 6px; }
  .stat-sub { font-size: 11px; color: var(--color-text-tertiary); margin-top: 4px; }
}
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
}
.channel-card {
  margin-bottom: 12px;
  padding: 14px;
}
.ch-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.ch-name {
  font-size: 14px;
  font-weight: 600;
}
.ch-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
  padding: 8px 0;
  border-top: 1px dashed var(--color-border-tertiary);
  border-bottom: 1px dashed var(--color-border-tertiary);
  margin-bottom: 10px;
  code {
    font-size: 11px;
    background: var(--color-background-secondary);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
  }
}
.ch-score {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}
.ch-score-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
.ch-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px dashed var(--color-border-tertiary);
}
.ch-test-time {
  font-size: 11px;
  color: var(--color-text-tertiary);
}
.score-legend {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--color-border-tertiary);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--color-text-secondary);
  span { margin-right: 10px; }
}
.form-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  line-height: 1.5;
  margin-top: 4px;
}
.type-cards {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  width: 100%;
}
.type-card {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  &:hover { background: var(--color-background-secondary); }
  &.selected {
    border-color: var(--color-border-info);
    background: var(--color-background-info);
  }
}
.type-card-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}
.type-card-desc {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}
.sender-block {
  margin: 4px -20px 18px;
  padding: 14px 20px 0;
  background: var(--color-background-secondary);
  border-top: 1px solid var(--color-border-tertiary);
  border-bottom: 1px solid var(--color-border-tertiary);
}
.sender-block-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 14px;
}
.switch-note {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-left: 10px;
}
.dns-guide {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: var(--color-background-secondary);
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.8;
}
.dns-guide-title {
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}
.dns-record {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  background: var(--color-background-primary);
  padding: 8px 10px;
  border-radius: 4px;
  margin-bottom: 6px;
  &:last-child { margin-bottom: 0; }
}
.dns-record-type {
  color: var(--color-text-info);
}
</style>
