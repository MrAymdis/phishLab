<template>
  <div class="page-container">
    <PageHeader title="系统设置" />

    <div class="card" style="margin: 16px">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="平台账号" name="accounts">
          <div class="card card-blue" style="margin: 0">
            <div class="card-title">
              登录用户管理
              <div style="display: flex; gap: 8px; align-items: center">
                <el-input v-model="accountKw" placeholder="用户名 / 姓名" clearable size="small"
                  style="width: 200px" @keyup.enter="loadAccounts(1)" @clear="loadAccounts(1)" />
                <el-button size="small" type="primary" @click="loadAccounts(1)">查询</el-button>
                <el-button size="small" type="success" :icon="Plus" @click="openAccountDialog()">新建账号</el-button>
              </div>
            </div>
            <el-table :data="accounts" v-loading="accountsLoading" size="default">
              <el-table-column prop="username" label="登录名" min-width="120" />
              <el-table-column prop="real_name" label="姓名" min-width="100" />
              <el-table-column label="角色" min-width="180">
                <template #default="{ row }">
                  <el-tag v-for="r in row.roles" :key="r.id" size="small" effect="plain"
                    style="margin-right: 4px">{{ r.name }}</el-tag>
                  <span v-if="!row.roles?.length" style="color: var(--color-text-tertiary); font-size: 12px">未分配</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
                    {{ row.status === 1 ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="最后登录" width="160">
                <template #default="{ row }">{{ row.last_login_at || '-' }}</template>
              </el-table-column>
              <el-table-column label="创建时间" width="160">
                <template #default="{ row }">{{ row.created_at }}</template>
              </el-table-column>
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" link type="primary" @click="openAccountDialog(row)">编辑</el-button>
                  <el-button size="small" link type="warning" @click="openResetPwd(row)">重置密码</el-button>
                  <el-button size="small" link :type="row.status === 1 ? 'danger' : 'success'"
                    @click="toggleAccountStatus(row)">
                    {{ row.status === 1 ? '禁用' : '启用' }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination style="margin-top: 12px; justify-content: flex-end"
              v-model:current-page="accountPage" :page-size="accountPageSize"
              :total="accountTotal" layout="total, prev, pager, next" @current-change="loadAccounts" />
          </div>

          <!-- 新建/编辑账号弹窗 -->
          <el-dialog v-model="accountDialog.show" :title="accountDialog.isEdit ? '编辑账号' : '新建平台账号'"
            width="460px">
            <el-form label-width="90px">
              <el-form-item label="登录名" required>
                <el-input v-model="accountForm.username" :disabled="accountDialog.isEdit"
                  placeholder="2-64 字符，唯一" />
              </el-form-item>
              <el-form-item label="姓名" required>
                <el-input v-model="accountForm.real_name" placeholder="真实姓名" />
              </el-form-item>
              <el-form-item v-if="!accountDialog.isEdit" label="初始密码" required>
                <el-input v-model="accountForm.password" type="password" show-password
                  placeholder="至少 8 位，PBKDF2 哈希存储" />
              </el-form-item>
              <el-form-item label="角色">
                <el-select v-model="accountForm.role_ids" multiple placeholder="分配角色（可多选）" style="width: 100%">
                  <el-option v-for="r in roleOptions" :key="r.id" :label="r.name" :value="r.id" />
                </el-select>
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button size="small" @click="accountDialog.show = false">取消</el-button>
              <el-button size="small" type="primary" :loading="accountSaving" @click="saveAccount">保存</el-button>
            </template>
          </el-dialog>
        </el-tab-pane>

        <el-tab-pane label="权限管理 (RBAC)" name="rbac">
          <el-row :gutter="12">
            <el-col :span="6">
              <div class="card card-blue" style="margin: 0">
                <div class="card-title">角色列表</div>
                <div style="margin-top: 8px">
                  <div
                    v-for="r in roles"
                    :key="r.id"
                    class="role-item"
                    :class="{ active: activeRole === r.id }"
                    @click="activeRole = r.id"
                  >
                    <div>
                      <div class="role-name">{{ r.name }}</div>
                      <div class="role-desc">{{ r.desc }}</div>
                    </div>
                    <el-tag size="small" effect="plain">{{ r.user_count }}人</el-tag>
                  </div>
                  <el-button size="small" type="primary" :icon="Plus" style="width: 100%; margin-top: 10px">
                    新建自定义角色
                  </el-button>
                </div>
              </div>
            </el-col>
            <el-col :span="18">
              <div class="card card-teal" style="margin: 0">
                <div class="card-title">权限配置 · {{ currentRoleName }}</div>
                <!-- 角色信息 -->
                <el-row :gutter="12">
                  <el-col :span="8">
                    <el-form-item label="角色名称" label-width="80px" size="small">
                      <el-input :model-value="currentRoleName" placeholder="角色名称" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="8">
                    <el-form-item label="角色标识" label-width="80px" size="small">
                      <el-input :model-value="currentRoleCode" placeholder="如 admin" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="8">
                    <el-form-item label="角色描述" label-width="80px" size="small">
                      <el-input :model-value="currentRoleDesc" placeholder="角色用途说明" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-divider style="margin: 8px 0 14px" />
                <!-- 菜单权限矩阵 -->
                <div class="sub-title">菜单权限矩阵</div>
                <el-table :data="permMatrix" size="small" border style="margin-top: 4px">
                  <el-table-column prop="menu" label="菜单 / 功能" min-width="180" />
                  <el-table-column label="查看" width="110" align="center">
                    <template #default="{ row }"><el-checkbox v-model="row.view" /></template>
                  </el-table-column>
                  <el-table-column label="编辑" width="110" align="center">
                    <template #default="{ row }"><el-checkbox v-model="row.edit" /></template>
                  </el-table-column>
                  <el-table-column label="删除" width="110" align="center">
                    <template #default="{ row }"><el-checkbox v-model="row.del" /></template>
                  </el-table-column>
                </el-table>
                <el-divider style="margin: 14px 0" />
                <!-- 数据权限 + 字段级权限 -->
                <el-row :gutter="12">
                  <el-col :span="12">
                    <div class="sub-title">数据权限范围</div>
                    <el-radio-group v-model="dataScope" size="small">
                      <el-radio-button value="all">全部数据</el-radio-button>
                      <el-radio-button value="dept">本部门及下级</el-radio-button>
                      <el-radio-button value="self">仅本人</el-radio-button>
                    </el-radio-group>
                    <el-select
                      v-if="dataScope === 'dept'"
                      v-model="customDepts"
                      multiple
                      collapse-tags
                      placeholder="自定义部门范围（可选）"
                      size="small"
                      style="width: 100%; margin-top: 10px"
                    >
                      <el-option v-for="d in deptOptions" :key="d" :label="d" :value="d" />
                    </el-select>
                  </el-col>
                  <el-col :span="12">
                    <div class="sub-title">字段级权限（敏感字段脱敏）</div>
                    <el-checkbox-group v-model="sensitiveFields">
                      <el-checkbox label="phone">手机号脱敏</el-checkbox>
                      <el-checkbox label="idcard">身份证脱敏</el-checkbox>
                      <el-checkbox label="salary">薪资隐藏</el-checkbox>
                      <el-checkbox label="risk_detail">风险详情仅本人可见</el-checkbox>
                    </el-checkbox-group>
                  </el-col>
                </el-row>
                <div style="margin-top: 16px">
                  <el-button type="primary">保存权限配置</el-button>
                  <el-button>重置</el-button>
                </div>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="审计日志" name="audit">
          <!-- 统计卡 + 过滤 -->
          <el-row :gutter="12" style="margin: 0 0 12px 0">
            <el-col :span="8"><StatCard title="今日操作数" value="342" accent="blue" /></el-col>
            <el-col :span="8"><StatCard title="本周操作数" value="2,156" accent="teal" /></el-col>
            <el-col :span="8"><StatCard title="异常操作数" value="7" accent="red" /></el-col>
          </el-row>
          <div class="card" style="margin: 0 0 12px 0">
            <div class="toolbar">
              <el-radio-group v-model="auditType" size="small">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="op">操作日志</el-radio-button>
                <el-radio-button value="login">登录日志</el-radio-button>
                <el-radio-button value="sys">系统日志</el-radio-button>
              </el-radio-group>
              <el-select v-model="auditUser" size="small" placeholder="操作人" clearable style="width: 140px">
                <el-option label="admin" value="admin" />
                <el-option label="operator01" value="operator01" />
                <el-option label="auditor02" value="auditor02" />
              </el-select>
              <el-select v-model="auditRange" size="small" placeholder="时间范围" style="width: 140px">
                <el-option label="今天" value="today" />
                <el-option label="近7天" value="7d" />
                <el-option label="近30天" value="30d" />
              </el-select>
              <el-input v-model="auditKw" size="small" placeholder="搜索操作内容" style="width: 200px" clearable />
              <el-button size="small" type="primary">查询</el-button>
              <el-button size="small">导出日志</el-button>
            </div>
          </div>

          <div class="card card-purple" style="margin: 0 0 12px 0">
            <div class="card-title">系统操作日志</div>
            <el-table :data="opLogs" size="small" style="margin-top: 8px">
              <el-table-column prop="time" label="时间" width="160" />
              <el-table-column prop="user" label="操作人" width="100" />
              <el-table-column prop="action" label="动作" width="160" />
              <el-table-column prop="target" label="目标对象" min-width="240" />
              <el-table-column prop="ip" label="IP地址" width="120" />
            </el-table>
            <el-pagination
              style="margin-top: 10px; justify-content: flex-end"
              layout="total, prev, pager, next"
              :total="opLogTotal"
              :page-size="5"
            />
          </div>
          <div class="card card-orange" style="margin: 0">
            <div class="card-title">登录日志</div>
            <el-table :data="loginLogs" size="small" style="margin-top: 8px">
              <el-table-column prop="time" label="时间" width="160" />
              <el-table-column prop="user" label="用户" width="100" />
              <el-table-column prop="ip" label="IP地址" width="120" />
              <el-table-column prop="browser" label="浏览器 / 系统" min-width="220" />
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.status === 'ok'" type="success" size="small" effect="dark">成功</el-tag>
                  <el-tag v-else type="danger" size="small" effect="dark">失败</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              style="margin-top: 10px; justify-content: flex-end"
              layout="total, prev, pager, next"
              :total="loginLogTotal"
              :page-size="5"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="系统集成" name="integration">
          <el-row :gutter="12" align="stretch">
            <el-col :span="24">
              <div class="card card-blue" style="margin: 0 0 12px 0">
                <div class="card-title">SSO 单点登录配置</div>
                <el-form label-width="140px" style="margin-top: 10px" size="default">
                  <el-form-item label="启用 SSO">
                    <el-switch v-model="ssoEnabled" />
                  </el-form-item>
                  <el-form-item label="协议类型">
                    <el-radio-group v-model="ssoType" :disabled="!ssoEnabled">
                      <el-radio value="oidc">OIDC (OAuth 2.0)</el-radio>
                      <el-radio value="saml2">SAML 2.0</el-radio>
                      <el-radio value="form">表单集成</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item v-if="ssoType === 'oidc' && ssoEnabled" label="Issuer (租户ID)">
                    <el-input placeholder="https://login.microsoftonline.com/{tenant-id}/v2.0" />
                  </el-form-item>
                  <el-form-item v-if="ssoType === 'oidc' && ssoEnabled" label="Client ID">
                    <el-input placeholder="应用程序(客户端)ID" />
                  </el-form-item>
                  <el-form-item v-if="ssoType === 'oidc' && ssoEnabled" label="回调地址">
                    <el-input value="https://phishlab.company.com/sso/callback" readonly />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" :disabled="!ssoEnabled">保存配置</el-button>
                    <el-button :disabled="!ssoEnabled">测试登录</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="card card-teal" style="margin: 0; height: 100%">
                <div class="card-title">SIEM Syslog 推送</div>
                <el-form label-width="100px" style="margin-top: 10px" size="small">
                  <el-form-item label="服务器">
                    <el-input v-model="siem.server" placeholder="siem.corp.local" />
                  </el-form-item>
                  <el-form-item label="端口">
                    <el-input-number v-model="siem.port" :min="1" :max="65535" />
                  </el-form-item>
                  <el-form-item label="协议">
                    <el-radio-group v-model="siem.proto">
                      <el-radio value="udp">UDP</el-radio>
                      <el-radio value="tcp">TCP</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item label="TLS 加密">
                    <el-switch v-model="siem.tls" />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" size="small">保存</el-button>
                    <el-button size="small">发送测试日志</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="card card-purple" style="margin: 0; height: 100%">
                <div class="card-title">Webhook 告警推送</div>
                <el-form label-width="100px" style="margin-top: 10px" size="small">
                  <el-form-item label="推送类型">
                    <el-radio-group v-model="wh.type">
                      <el-radio value="wecom">企业微信</el-radio>
                      <el-radio value="dingtalk">钉钉</el-radio>
                      <el-radio value="feishu">飞书</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item label="Webhook URL">
                    <el-input v-model="wh.url" type="textarea" :rows="2" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
                  </el-form-item>
                  <el-form-item label="签名密钥">
                    <el-input v-model="wh.secret" type="password" show-password
                      placeholder="选填，AES-GCM 加密存储" />
                    <div style="font-size: 11px; color: var(--color-text-tertiary); margin-top: 4px">
                      留空保存表示不修改已配置的密钥
                    </div>
                  </el-form-item>
                  <el-form-item label="推送事件">
                    <el-checkbox-group v-model="wh.events">
                      <el-checkbox label="campaign_start">演练开始</el-checkbox>
                      <el-checkbox label="high_risk">高危中招</el-checkbox>
                      <el-checkbox label="campaign_end">演练结束</el-checkbox>
                      <el-checkbox label="report">员工举报</el-checkbox>
                    </el-checkbox-group>
                  </el-form-item>
                  <el-form-item label="启用推送">
                    <el-switch v-model="wh.enabled" />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" size="small" :loading="whSaving" @click="saveWebhook">保存</el-button>
                    <el-button size="small" :loading="whTesting" @click="testWebhook">发送测试</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="基础参数" name="basic">
          <el-row :gutter="12" align="stretch">
            <el-col :span="12">
              <div class="card card-green" style="margin: 0; height: 100%">
                <div class="card-title">平台信息</div>
                <el-form label-width="100px" style="margin-top: 12px" size="default">
                  <el-form-item label="平台 Logo">
                    <el-upload
                      class="logo-uploader"
                      :show-file-list="false"
                      :auto-upload="true"
                      :http-request="uploadLogo"
                      accept="image/*"
                    >
                      <img v-if="brand.logo" :src="logoPreview" class="logo-preview" alt="平台 Logo" />
                      <div v-else class="logo-placeholder">
                        <el-icon :size="28" color="#67c23a"><Picture /></el-icon>
                        <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 4px">点击上传 200x60</div>
                      </div>
                    </el-upload>
                  </el-form-item>
                  <el-form-item label="平台名称">
                    <el-input v-model="brand.name" />
                  </el-form-item>
                  <el-form-item label="版权信息">
                    <el-input v-model="brand.copyright" placeholder="© 2026 公司名称 版权所有" />
                  </el-form-item>
                  <el-form-item label="备案号">
                    <el-input v-model="brand.icp" placeholder="京ICP备00000000号" />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" size="small" @click="saveBrand">保存品牌设置</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="card card-red" style="margin: 0; height: 100%">
                <div class="card-title">隐私与合规</div>
                <el-form label-width="120px" style="margin-top: 12px" size="default">
                  <el-form-item label="数据留存策略">
                    <div style="display: flex; flex-direction: column; gap: 8px; width: 100%">
                      <div class="retention-row">
                        <span>演练数据</span>
                        <el-select v-model="privacy.retention_drill" size="small" style="width: 150px">
                          <el-option label="90 天" value="90d" />
                          <el-option label="180 天" value="180d" />
                          <el-option label="1 年" value="1y" />
                        </el-select>
                      </div>
                      <div class="retention-row">
                        <span>员工行为数据</span>
                        <el-select v-model="privacy.retention_behavior" size="small" style="width: 150px">
                          <el-option label="90 天" value="90d" />
                          <el-option label="180 天" value="180d" />
                          <el-option label="1 年" value="1y" />
                        </el-select>
                      </div>
                      <div class="retention-row">
                        <span>日志数据</span>
                        <el-select v-model="privacy.retention_log" size="small" style="width: 150px">
                          <el-option label="180 天" value="180d" />
                          <el-option label="1 年" value="1y" />
                          <el-option label="3 年（等保要求）" value="3y" />
                        </el-select>
                      </div>
                    </div>
                  </el-form-item>
                  <el-form-item label="演练免责声明">
                    <el-input v-model="privacy.disclaimer" type="textarea" :rows="3"
                      placeholder="演练仅用于安全意识教育目的，所有收集数据将在演练结束后按留存策略销毁..." />
                  </el-form-item>
                  <el-form-item label="取证操作密码">
                    <el-input
                      v-model="privacy.reveal_operation_pwd"
                      type="password"
                      show-password
                      :placeholder="revealPwdConfigured ? '已配置（留空表示不修改）' : '设置后用于取证查看提交明文'"
                    />
                    <div style="font-size: 11px; color: var(--color-text-tertiary); line-height: 1.6; margin-top: 4px">
                      查看员工提交的口令明文前需输入此密码，PBKDF2 哈希存储，解密操作全程留审计
                    </div>
                  </el-form-item>
                  <el-form-item>
                    <el-checkbox v-model="privacy.compliance_confirm">
                      已确认符合《网络安全法》《个人信息保护法》及公司合规要求
                    </el-checkbox>
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" size="small" @click="savePrivacy">保存合规设置</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="授权管理" name="license">
          <el-row :gutter="12">
            <el-col :span="6" v-for="s in licenseStats" :key="s.title">
              <div class="card" :class="`card-${s.accent}`" style="margin: 0">
                <div class="card-title">{{ s.title }}</div>
                <div class="lic-value">{{ s.value }}</div>
                <div v-if="s.progress !== undefined" style="margin-top: 8px">
                  <el-progress
                    :percentage="s.progress"
                    :stroke-width="8"
                    :format="() => `${s.used}/${s.total}`"
                  />
                </div>
                <div v-if="s.sub" class="lic-sub">{{ s.sub }}</div>
              </div>
            </el-col>
          </el-row>

          <div class="card card-purple" style="margin: 12px 0 0 0">
            <div class="card-title">功能模块授权</div>
            <el-table :data="moduleRows" size="small" style="margin-top: 8px" :show-header="false">
              <el-table-column prop="name" width="200" />
              <el-table-column label="授权级别" width="180">
                <template #default="{ row }">
                  <el-tag v-if="row.level === 'flagship'" type="danger" effect="dark">旗舰版</el-tag>
                  <el-tag v-else-if="row.level === 'pro'" type="warning" effect="dark">标准版</el-tag>
                  <el-tag v-else type="success" effect="dark">全部版本</el-tag>
                </template>
              </el-table-column>
              <el-table-column>
                <template #default="{ row }">
                  <el-switch v-model="row.enabled" :disabled="row.locked" />
                  <span style="font-size: 11px; color: var(--color-text-tertiary); margin-left: 8px">
                    {{ row.locked ? `当前授权不包含，需升级到${row.level === 'flagship' ? '旗舰版' : '标准版'}` : '已启用' }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="card card-orange" style="margin: 12px 0 0 0">
            <div class="card-title">激活管理</div>
            <el-row :gutter="12" style="margin-top: 10px">
              <el-col :span="8">
                <div class="activate-card">
                  <div class="act-title"><el-icon :size="16"><Link /></el-icon> 在线激活</div>
                  <el-input v-model="actCode" placeholder="请输入激活码" style="margin-top: 10px" />
                  <el-button type="primary" style="width: 100%; margin-top: 10px" :icon="Check">验证激活</el-button>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="activate-card">
                  <div class="act-title"><el-icon :size="16"><UploadFilled /></el-icon> 离线激活</div>
                  <el-upload
                    action="#"
                    :auto-upload="false"
                    :show-file-list="false"
                    style="margin-top: 10px"
                  >
                    <div class="upload-btn">
                      <el-icon :size="22"><FolderOpened /></el-icon>
                      <div style="font-size: 12px; margin-top: 4px">上传 .lic 授权文件</div>
                    </div>
                  </el-upload>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="activate-card">
                  <div class="act-title"><el-icon :size="16"><Phone /></el-icon> 联系销售</div>
                  <div style="font-size: 12px; color: var(--color-text-secondary); margin-top: 10px; line-height: 1.8">
                    <div>销售热线：400-000-8888</div>
                    <div>商务邮箱：sales@phishlab.com</div>
                    <div>技术支持：support@phishlab.com</div>
                  </div>
                  <el-button style="width: 100%; margin-top: 10px">获取报价单</el-button>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import {
  Plus, Picture, Link, Check, UploadFilled, FolderOpened, Phone,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi, systemApi } from '@/api'
import { useBrand } from '@/composables/useBrand'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'

const activeTab = ref('rbac')
const { updateBrand } = useBrand()

// ---- 平台账号管理 ----
const accounts = ref<{
  id: number; username: string; real_name: string; status: number;
  last_login_at: string | null; created_at: string; roles: { id: number; name: string }[];
}[]>([])
const accountTotal = ref(0)
const accountPage = ref(1)
const accountPageSize = 10
const accountKw = ref('')
const accountsLoading = ref(false)
const accountDialog = reactive({ show: false, isEdit: false })
const accountForm = reactive({ id: 0, username: '', real_name: '', password: '', role_ids: [] as number[] })
const accountSaving = ref(false)
const roleOptions = computed(() => roles.value.map(r => ({ id: r.id, name: r.name })))

async function loadAccounts(page = accountPage.value) {
  accountPage.value = page
  accountsLoading.value = true
  try {
    const data = await accountApi.list({ page, pageSize: accountPageSize, kw: accountKw.value })
    accounts.value = data?.list ?? []
    accountTotal.value = data?.total ?? 0
  } catch {
    ElMessage.error('账号列表加载失败')
  } finally {
    accountsLoading.value = false
  }
}
function openAccountDialog(row?: { id: number; username: string; real_name: string; roles: { id: number }[] }) {
  accountDialog.isEdit = !!row
  accountDialog.show = true
  accountForm.id = row?.id ?? 0
  accountForm.username = row?.username ?? ''
  accountForm.real_name = row?.real_name ?? ''
  accountForm.password = ''
  accountForm.role_ids = row?.roles?.map(r => r.id) ?? []
}
async function saveAccount() {
  if (!accountForm.username.trim() || !accountForm.real_name.trim()) {
    ElMessage.warning('登录名与姓名必填')
    return
  }
  if (!accountDialog.isEdit && accountForm.password.length < 8) {
    ElMessage.warning('初始密码至少 8 位')
    return
  }
  accountSaving.value = true
  try {
    if (accountDialog.isEdit) {
      await accountApi.update(accountForm.id, {
        real_name: accountForm.real_name, role_ids: accountForm.role_ids, status: 1,
      })
    } else {
      await accountApi.create({
        username: accountForm.username.trim(), real_name: accountForm.real_name.trim(),
        password: accountForm.password, role_ids: accountForm.role_ids,
      })
    }
    ElMessage.success(accountDialog.isEdit ? '账号已更新' : '账号已创建')
    accountDialog.show = false
    loadAccounts()
  } catch (err) {
    ElMessage.error(`保存失败：${err instanceof Error ? err.message : String(err)}`)
  } finally {
    accountSaving.value = false
  }
}
function openResetPwd(row: { id: number; username: string }) {
  ElMessageBox.prompt(`重置「${row.username}」的密码`, '重置密码', {
    inputType: 'password', inputPlaceholder: '新密码（至少 8 位）',
    inputValidator: (v: string) => (v.length >= 8 ? true : '密码至少 8 位'),
  }).then(async ({ value }) => {
    try {
      await accountApi.resetPassword(row.id, value)
      ElMessage.success('密码已重置')
    } catch (err) {
      ElMessage.error(`重置失败：${err instanceof Error ? err.message : String(err)}`)
    }
  }).catch(() => {})
}
function toggleAccountStatus(row: { id: number; username: string; real_name: string; status: number; roles: { id: number }[] }) {
  const next = row.status === 1 ? 0 : 1
  ElMessageBox.confirm(`确定${next === 0 ? '禁用' : '启用'}账号「${row.username}」吗？`,
    next === 0 ? '禁用账号' : '启用账号', { type: 'warning' })
    .then(async () => {
      try {
        // update 为覆盖式：切换状态需同时回传姓名与角色，避免清空
        await accountApi.update(row.id, { real_name: row.real_name, role_ids: row.roles?.map(r => r.id) ?? [], status: next })
        ElMessage.success(next === 0 ? '已禁用' : '已启用')
        loadAccounts()
      } catch (err) {
        ElMessage.error(`操作失败：${err instanceof Error ? err.message : String(err)}`)
      }
    }).catch(() => {})
}
const activeRole = ref(1)
const ssoEnabled = ref(true)
const ssoType = ref('oidc')
const whSaving = ref(false)
const whTesting = ref(false)
const dataScope = ref('dept')
const sensitiveFields = ref(['phone', 'risk_detail'])
const customDepts = ref<string[]>([])
const actCode = ref('')

// 审计日志过滤
const auditType = ref('all')
const auditUser = ref('')
const auditRange = ref('7d')
const auditKw = ref('')

const deptOptions = ['技术部', '财务部', '市场部', '人力资源部', '行政部', '销售部', '产品部', '法务合规部']

const brand = reactive({
  name: '企业防钓鱼演练平台',
  logo: '',
  copyright: '© 2026 公司信息安全部 版权所有',
  icp: '京ICP备2026000000号-1',
})
const privacy = reactive({
  retention_drill: '180d',
  retention_behavior: '180d',
  retention_log: '1y',
  disclaimer: '本平台所有钓鱼演练活动仅用于企业内部安全意识教育目的。演练中收集的所有行为数据（打开、点击、提交、下载等）将严格保密，仅用于评估员工安全意识水平，并在数据留存周期到期后自动销毁。所有演练不涉及真实的恶意行为。',
  compliance_confirm: true,
  reveal_operation_pwd: '',
})
/** 取证操作密码是否已配置（GET 只回显 "1"，绝不回显哈希） */
const revealPwdConfigured = ref(false)
const siem = reactive({ server: 'siem.corp.local', port: 514, proto: 'udp', tls: false })
const wh = reactive({
  type: 'wecom',
  url: '',
  secret: '',
  events: ['high_risk', 'campaign_end', 'report'],
  enabled: false,
})

const mockRoles = [
  { id: 1, name: '超级管理员', code: 'super_admin', desc: '拥有所有权限', user_count: 3 },
  { id: 2, name: '演练操作员', code: 'drill_operator', desc: '可发起/管理演练与素材', user_count: 8 },
  { id: 3, name: '只读审计员', code: 'readonly_auditor', desc: '仅可查看报表与日志', user_count: 5 },
  { id: 4, name: '部门安全接口人', code: 'dept_security', desc: '仅查看本部门数据', user_count: 12 },
]
const roles = ref<{ id: number; name: string; code: string; desc: string; user_count: number; data_scope?: string }[]>(mockRoles)
const currentRole = computed(() => roles.value.find(r => r.id === activeRole.value))
const currentRoleName = computed(() => currentRole.value?.name)
const currentRoleCode = computed(() => currentRole.value?.code)
const currentRoleDesc = computed(() => currentRole.value?.desc)

// 菜单权限矩阵（菜单 × 查看/编辑/删除）
const permMatrix = reactive([
  { menu: '数据概览', view: true, edit: false, del: false },
  { menu: '演练管理', view: true, edit: true, del: false },
  { menu: '素材模板', view: true, edit: true, del: false },
  { menu: '发送配置', view: true, edit: false, del: false },
  { menu: '用户和组', view: true, edit: false, del: false },
  { menu: '安全培训', view: true, edit: true, del: false },
  { menu: '数据报表', view: true, edit: false, del: false },
  { menu: '邮件举报', view: true, edit: true, del: false },
  { menu: '系统设置', view: false, edit: false, del: false },
])

const opLogs = ref([
  { time: '2026-08-15 14:33:12', user: 'admin', action: '发起演练', target: 'Q3全员防钓鱼演练 (ID: 2026-Q3-ALL)', ip: '10.0.1.22' },
  { time: '2026-08-15 11:20:05', user: 'operator01', action: '编辑邮件模板', target: '【财务通知】报销截止提醒', ip: '10.0.1.45' },
  { time: '2026-08-15 09:58:41', user: 'auditor02', action: '导出报表', target: '2026 Q2 部门风险汇总.xlsx', ip: '10.0.2.88' },
  { time: '2026-08-14 18:05:22', user: 'admin', action: '更新系统设置', target: '数据留存周期 90天 → 180天', ip: '10.0.1.22' },
  { time: '2026-08-14 15:42:08', user: 'operator01', action: '新增发送通道', target: '备用SMTP (smtp2.company.com)', ip: '10.0.1.45' },
])
const opLogTotal = ref(1286)
const loginLogs = ref([
  { time: '2026-08-16 09:02:18', user: 'admin', ip: '10.0.1.22', browser: 'Chrome 125 · Windows 10', status: 'ok' },
  { time: '2026-08-16 08:55:44', user: 'operator01', ip: '10.0.1.45', browser: 'Edge 125 · Windows 11', status: 'ok' },
  { time: '2026-08-16 08:50:12', user: 'unknown', ip: '202.108.x.x', browser: 'Chrome 120 · macOS', status: 'fail' },
  { time: '2026-08-15 20:15:33', user: 'auditor02', ip: '10.0.2.88', browser: 'Safari 17 · macOS 14', status: 'ok' },
  { time: '2026-08-15 20:14:01', user: 'auditor02', ip: '10.0.2.88', browser: 'Safari 17 · macOS 14', status: 'fail' },
])
const loginLogTotal = ref(3542)

type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
const mockLicenseStats: { title: string; value: string; accent: Accent; sub?: string; progress?: number; used?: string; total?: string }[] = [
  { title: '授权状态', value: '试用版 Trial', accent: 'orange', sub: '剩余 14 天 · 到期 2026-08-30' },
  { title: '到期时间', value: '2026-08-30', accent: 'red', sub: '请提前 30 天完成续期' },
  { title: '用户配额', value: '活跃 2,180 / 5,000', accent: 'blue', progress: 44, used: '2180', total: '5000' },
  { title: '邮件发送量', value: '本月 18.2万 / 30万', accent: 'green', progress: 61, used: '18.2万', total: '30万' },
]
const licenseStats = ref(mockLicenseStats)

const moduleRows = [
  { name: 'AI 智能生成模块', level: 'flagship', enabled: false, locked: true },
  { name: 'API 开放平台', level: 'flagship', enabled: false, locked: true },
  { name: '载荷管理（EXE/宏）', level: 'flagship', enabled: false, locked: true },
  { name: '在线培训 LMS 模块', level: 'pro', enabled: true, locked: false },
  { name: '短信钓鱼通道', level: 'pro', enabled: true, locked: false },
  { name: '邮件钓鱼演练核心', level: 'all', enabled: true, locked: false },
  { name: '报表与导出', level: 'all', enabled: true, locked: false },
]

// ---- 接口数据加载（失败降级为演示数据）----
const loadWarning = () => ElMessage.warning('接口数据加载失败，已展示演示数据')
const toFlag = (v: unknown) => v === '1' || v === 1 || v === true

// ---- 保存（基础参数 → platform_setting）----
const logoBust = ref(0)
/** Logo 预览地址：上传替换后拼时间戳，规避浏览器缓存旧图 */
const logoPreview = computed(() => (brand.logo ? `${brand.logo}?v=${logoBust.value}` : ''))
const uploadLogo = async (opt: { file: File }) => {
  try {
    const res = (await systemApi.uploadLogo(opt.file)) as { logo?: string }
    if (res?.logo) {
      brand.logo = res.logo
      logoBust.value = Date.now()
      updateBrand({ logo: res.logo }) // 侧边栏/登录页（同会话）立即生效
    }
    ElMessage.success('平台 Logo 已更新')
  } catch (err) {
    ElMessage.error(`上传失败：${err instanceof Error ? err.message : String(err)}`)
  }
}
const saveBrand = async () => {
  try {
    await systemApi.updateSettings({
      name: brand.name, copyright: brand.copyright, icp: brand.icp,
    })
    ElMessage.success('品牌设置已保存')
  } catch (err) {
    ElMessage.error(`保存失败：${err instanceof Error ? err.message : String(err)}`)
  }
}
const savePrivacy = async () => {
  try {
    const payload: Record<string, unknown> = {
      retention_drill: privacy.retention_drill,
      retention_behavior: privacy.retention_behavior,
      retention_log: privacy.retention_log,
      disclaimer: privacy.disclaimer,
      compliance_confirm: privacy.compliance_confirm ? '1' : '0',
    }
    // 留空 = 不修改既有操作密码；输入则覆盖（后端 PBKDF2 哈希存储）
    if (privacy.reveal_operation_pwd) payload.reveal_operation_pwd = privacy.reveal_operation_pwd
    await systemApi.updateSettings(payload)
    if (privacy.reveal_operation_pwd) {
      revealPwdConfigured.value = true
      privacy.reveal_operation_pwd = ''
    }
    ElMessage.success('合规设置已保存')
  } catch (err) {
    ElMessage.error(`保存失败：${err instanceof Error ? err.message : String(err)}`)
  }
}

// ---- Webhook 告警推送 ----
async function loadWebhook() {
  try {
    const data = (await systemApi.webhooks()) as { im_type: string; url: string; event_types: string[]; enabled: number }[]
    if (Array.isArray(data) && data.length) {
      const w = data[0]
      wh.type = w.im_type || 'wecom'
      wh.url = w.url
      wh.events = w.event_types ?? []
      wh.enabled = !!w.enabled
    }
  } catch { /* 未配置时保持空表单 */ }
}
async function saveWebhook() {
  if (!wh.url.trim()) { ElMessage.warning('请填写 Webhook URL'); return }
  if (!wh.events.length) { ElMessage.warning('请至少选择一类推送事件'); return }
  whSaving.value = true
  try {
    await systemApi.saveWebhook({
      name: '安全告警推送', im_type: wh.type, url: wh.url.trim(),
      secret: wh.secret, event_types: wh.events, enabled: wh.enabled ? 1 : 0,
    })
    wh.secret = ''
    ElMessage.success('Webhook 配置已保存')
  } catch (err) {
    ElMessage.error(`保存失败：${err instanceof Error ? err.message : String(err)}`)
  } finally {
    whSaving.value = false
  }
}
async function testWebhook() {
  if (!wh.url.trim()) { ElMessage.warning('请先填写 Webhook URL'); return }
  whTesting.value = true
  try {
    const r = await systemApi.testWebhook({ im_type: wh.type, url: wh.url.trim(), secret: wh.secret })
    if (r.ok) ElMessage.success(`测试推送成功（HTTP ${r.status}）`)
    else ElMessage.error(`测试失败：${r.message}`)
  } catch (err) {
    ElMessage.error(`测试失败：${err instanceof Error ? err.message : String(err)}`)
  } finally {
    whTesting.value = false
  }
}

onMounted(async () => {
  loadAccounts()
  loadWebhook()
  // 角色列表
  try {
    const data = (await systemApi.roles()) as { id: number; code: string; name: string; data_scope?: string; remark?: string; user_count?: number }[]
    if (Array.isArray(data) && data.length) {
      roles.value = data.map((r, i) => ({
        id: r.id,
        name: r.name,
        code: r.code,
        desc: r.remark || '角色',
        user_count: r.user_count ?? mockRoles[i]?.user_count ?? 0,
        data_scope: r.data_scope,
      }))
    }
  } catch { loadWarning() }

  // 操作日志
  try {
    const data = (await systemApi.auditLogs({ page: 1, pageSize: 20 })) as { list: any[]; total?: number }
    if (Array.isArray(data?.list) && data.list.length) {
      opLogs.value = data.list.map(l => ({ time: l.time, user: l.user, action: l.action, target: l.target, ip: l.ip }))
      opLogTotal.value = data.total ?? opLogs.value.length
    }
  } catch { loadWarning() }

  // 登录日志
  try {
    const data = (await systemApi.loginLogs({ page: 1, pageSize: 20 })) as { list: any[]; total?: number }
    if (Array.isArray(data?.list) && data.list.length) {
      loginLogs.value = data.list.map(l => ({ time: l.time, user: l.user, ip: l.ip, browser: l.browser, status: l.status }))
      loginLogTotal.value = data.total ?? loginLogs.value.length
    }
  } catch { loadWarning() }

  // 基础参数（品牌/追踪/隐私合规）
  try {
    const s = (await systemApi.settings()) as Record<string, any>
    if (s && typeof s === 'object') {
      if (s.name) brand.name = s.name
      if (s.logo) brand.logo = s.logo
      if (s.copyright) brand.copyright = s.copyright
      if (s.icp) brand.icp = s.icp
      if (s.retention_drill) privacy.retention_drill = s.retention_drill
      if (s.retention_behavior) privacy.retention_behavior = s.retention_behavior
      if (s.retention_log) privacy.retention_log = s.retention_log
      if (s.disclaimer) privacy.disclaimer = s.disclaimer
      if (s.compliance_confirm !== undefined && s.compliance_confirm !== null) privacy.compliance_confirm = toFlag(s.compliance_confirm)
      if (s.reveal_operation_pwd) revealPwdConfigured.value = true
      // 同步到共享品牌（侧边栏/登录页）
      updateBrand({ name: brand.name, logo: brand.logo, copyright: brand.copyright, icp: brand.icp })
    }
  } catch { loadWarning() }

  // 授权信息
  try {
    const lic = (await systemApi.license()) as any
    if (lic && typeof lic === 'object') {
      const editionLabel: Record<string, string> = { trial: '试用版 Trial', standard: '标准版', flagship: '旗舰版' }
      const stats = [...mockLicenseStats]
      if (lic.edition) {
        stats[0] = {
          title: '授权状态', value: editionLabel[lic.edition] ?? lic.edition, accent: 'orange',
          sub: `剩余 ${lic.remaining_days ?? '-'} 天 · 到期 ${lic.expire_at ?? '-'}`,
        }
      }
      if (lic.expire_at) stats[1] = { title: '到期时间', value: lic.expire_at, accent: 'red', sub: '请提前 30 天完成续期' }
      const userQ = lic.quotas?.user
      if (userQ?.total) {
        stats[2] = {
          title: '用户配额', value: `活跃 ${userQ.used.toLocaleString()} / ${userQ.total.toLocaleString()}`, accent: 'blue',
          progress: Math.round((userQ.used / userQ.total) * 100), used: String(userQ.used), total: String(userQ.total),
        }
      }
      const mailQ = lic.quotas?.mail
      if (mailQ?.total) {
        stats[3] = {
          title: '邮件发送量', value: `本月 ${mailQ.used.toLocaleString()} / ${mailQ.total.toLocaleString()}`, accent: 'green',
          progress: Math.round((mailQ.used / mailQ.total) * 100), used: String(mailQ.used), total: String(mailQ.total),
        }
      }
      licenseStats.value = stats
    }
  } catch { loadWarning() }

  // Webhook 告警推送（onMounted 开头已由 loadWebhook() 加载，此处为重构前冗余代码，已删除）

  // SIEM Syslog 推送
  try {
    const cfg = (await systemApi.siem()) as any
    if (cfg && cfg.host) {
      siem.server = cfg.host
      if (cfg.port) siem.port = Number(cfg.port)
      if (['udp', 'tcp'].includes(cfg.protocol)) siem.proto = cfg.protocol
    }
  } catch { loadWarning() }
})
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.retention-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.role-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  &:hover { background: var(--color-background-secondary); }
  &.active { background: var(--color-primary-light-9); }
}
.role-name {
  font-size: 13px;
  font-weight: 600;
}
.role-desc {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.sub-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}
.lic-value {
  font-size: 20px;
  font-weight: 600;
  margin-top: 6px;
}
.lic-sub {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 6px;
}
.activate-card {
  padding: 14px;
  background: var(--color-background-secondary);
  border-radius: 8px;
  min-height: 160px;
}
.act-title {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
.upload-btn {
  border: 1px dashed var(--color-border-secondary);
  border-radius: 8px;
  padding: 18px;
  text-align: center;
  color: var(--color-text-secondary);
  cursor: pointer;
  &:hover { border-color: var(--color-primary); color: var(--color-primary); }
}
.logo-uploader {
  :deep(.el-upload) {
    width: 100%;
  }
}
.logo-preview {
  width: 200px;
  height: 60px;
  object-fit: contain;
  border: 1px dashed var(--color-border-secondary);
  border-radius: 8px;
  cursor: pointer;
  &:hover { border-color: var(--color-primary); }
}
.logo-placeholder {
  width: 200px;
  height: 60px;
  border: 1px dashed var(--color-border-secondary);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  &:hover { border-color: var(--color-primary); color: var(--color-primary); }
}
</style>
