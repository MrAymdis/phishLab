<template>
  <div class="page-container">
    <PageHeader title="安全培训">
      <template #actions>
        <el-button size="small" type="primary" :icon="VideoPlay" @click="openCourseDialog()">新建课程</el-button>
        <el-button size="small" :icon="Calendar" @click="openTaskDialog()">新建培训任务</el-button>
        <el-button size="small" :icon="Collection" @click="openQuestionDialog()">新建题目</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab" style="margin: 8px 16px 0">
      <el-tab-pane label="培训课程库" name="course">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="6"><StatCard title="课程总数" :value="courseStats.total" accent="blue" /></el-col>
          <el-col :span="6"><StatCard title="视频课程" :value="courseStats.video" accent="teal" /></el-col>
          <el-col :span="6"><StatCard title="图文/PDF课程" :value="courseStats.article + courseStats.pdf" accent="green" /></el-col>
          <el-col :span="6"><StatCard title="互动课程" :value="courseStats.interactive" accent="purple" /></el-col>
        </el-row>
        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-blue">
              <div class="toolbar">
                <el-input v-model="courseKw" size="small" placeholder="搜索课程名称" style="width: 240px" clearable />
                <el-radio-group v-model="categoryFilter" size="small">
                  <el-radio-button value="">全部</el-radio-button>
                  <el-radio-button value="video">视频</el-radio-button>
                  <el-radio-button value="article">图文</el-radio-button>
                  <el-radio-button value="pdf">PDF</el-radio-button>
                  <el-radio-button value="interactive">互动式</el-radio-button>
                </el-radio-group>
                <el-radio-group v-model="levelFilter" size="small">
                  <el-radio-button value="">全部难度</el-radio-button>
                  <el-radio-button value="easy">初级</el-radio-button>
                  <el-radio-button value="mid">中级</el-radio-button>
                  <el-radio-button value="hard">高级</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24" v-if="!filteredCourses.length">
            <el-empty description="暂无符合条件的课程" :image-size="80" />
          </el-col>
          <el-col :span="8" v-for="c in filteredCourses" :key="c.id">
            <div class="card course-card" :class="`card-${c.accent}`" @click="previewCourse(c)">
              <div class="course-cover" :style="{ background: c.coverBg }">
                <img v-if="c.cover_url" :src="c.cover_url" class="cover-img" alt="" />
                <span v-if="!c.cover_url" class="cover-icon">{{ c.coverIcon }}</span>
                <el-tag size="small" class="cover-tag" :type="c.tagType">{{ c.typeLabel }}</el-tag>
              </div>
              <div class="course-body">
                <div class="course-title">{{ c.title }}</div>
                <div class="course-meta">
                  <span><el-icon><Clock /></el-icon> {{ c.duration }} 分钟</span>
                  <span>
                    课件：
                    <el-link v-if="c.content_url" type="primary" :href="c.content_url" target="_blank">{{ c.material || '查看课件' }}</el-link>
                    <template v-else>{{ c.material || '未指定' }}</template>
                  </span>
                  <el-tag size="small" :type="levelTagType(c.level)" effect="plain">{{ levelLabel(c.level) }}</el-tag>
                </div>
                <div class="course-stats">
                  <div class="stat">
                    <div class="stat-val">{{ c.learners.toLocaleString() }}</div>
                    <div class="stat-label">学习人数</div>
                  </div>
                  <div class="stat">
                    <div class="stat-val">{{ c.completion }}%</div>
                    <div class="stat-label">平均完成度</div>
                  </div>
                </div>
                <div class="course-actions">
                  <el-button size="small" link type="primary" @click.stop="previewCourse(c)">预览</el-button>
                  <el-button size="small" link @click.stop="openCourseDialog(c)">编辑</el-button>
                  <el-button size="small" link type="danger" @click.stop="removeCourse(c)">删除</el-button>
                  <el-divider direction="vertical" />
                  <el-button size="small" link type="success" @click.stop="openTaskDialog(c.id)">新建任务用此课程</el-button>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="培训任务管理" name="task">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="8"><StatCard title="进行中计划" :value="taskStats.running" accent="green" /></el-col>
          <el-col :span="8"><StatCard title="已完成计划" :value="taskStats.completed" accent="blue" /></el-col>
          <el-col :span="8"><StatCard title="覆盖人员总数" :value="taskStats.totalPeople" accent="teal" /></el-col>
        </el-row>
        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-green">
              <div class="toolbar">
                <el-button size="small" type="primary" :icon="Plus" @click="openTaskDialog()">新建培训任务</el-button>
                <el-input v-model="taskKw" size="small" placeholder="搜索任务名称" style="width: 220px; margin-left: 12px" clearable />
              </div>
              <el-table :data="filteredTasks" size="small" style="margin-top: 12px">
                <el-table-column label="任务名称" min-width="200">
                  <template #default="{ row }">
                    <el-link type="primary" @click="viewTaskDetail(row)">{{ row.name }}</el-link>
                  </template>
                </el-table-column>
                <el-table-column label="关联课程" prop="course" min-width="180" />
                <el-table-column label="分配对象" min-width="200">
                  <template #default="{ row }">
                    {{ row.target }}（{{ row.count }} 人）
                  </template>
                </el-table-column>
                <el-table-column label="开始日期" prop="start" width="110" />
                <el-table-column label="截止日期" prop="end" width="110" />
                <el-table-column label="进度" min-width="220">
                  <template #default="{ row }">
                    <div class="task-progress">
                      <el-progress :percentage="row.progress" :stroke-width="8" color="#10B981" />
                      <div class="progress-detail">
                        已开始 {{ row.started }}人 · 已完成 {{ row.done }}人
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.status === 'running'" type="success" size="small">进行中</el-tag>
                    <el-tag v-else-if="row.status === 'completed'" size="small">已完成</el-tag>
                    <el-tag v-else-if="row.status === 'closed'" type="info" size="small" effect="plain">已关闭</el-tag>
                    <el-tag v-else type="danger" size="small">已过期</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="260" fixed="right">
                  <template #default="{ row }">
                    <el-button link size="small" type="primary" @click="viewTaskDetail(row)">详情</el-button>
                    <el-button link size="small" type="warning" v-if="row.status === 'running'" @click="remindTask(row)">催办</el-button>
                    <el-button link size="small" type="danger" v-if="row.status === 'running'" @click="closeTask(row)">关闭</el-button>
                    <el-button link size="small" @click="exportTask(row)">导出明细</el-button>
                    <el-button link size="small" type="danger" @click="removeTask(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!filteredTasks.length" description="暂无培训任务" :image-size="60" style="margin-top: 12px" />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="考试与测评" name="exam">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="6"><StatCard title="题库总数" :value="questionRows.length" suffix=" 道" accent="blue" /></el-col>
          <el-col :span="6"><StatCard title="试卷总数" :value="paperRows.length" suffix=" 份" accent="purple" /></el-col>
          <el-col :span="6"><StatCard title="本月考试次数" :value="examStats.monthTotal" accent="teal" /></el-col>
          <el-col :span="6">
            <div class="card card-orange" style="height: 100%; display: flex; align-items: center; justify-content: center">
              <el-button type="primary" :icon="Plus" @click="openQuestionDialog()">新建题目</el-button>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-red">
              <div class="card-title">
                题目列表
                <el-input v-model="questionKw" size="small" placeholder="搜索题干" style="width: 220px; margin-left: 12px" clearable />
              </div>
              <el-table :data="filteredQuestions" size="small" style="margin-top: 8px">
                <el-table-column label="题型" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.type === 'single'" type="primary" size="small">单选</el-tag>
                    <el-tag v-else-if="row.type === 'multi'" type="warning" size="small">多选</el-tag>
                    <el-tag v-else type="info" size="small">判断</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="题干" min-width="320" prop="content" show-overflow-tooltip />
                <el-table-column label="答案选项" min-width="200">
                  <template #default="{ row }">
                    <span v-if="row.type === 'judge'">正确 / 错误</span>
                    <span v-else>{{ row.options }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="难度" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.diff === 'hard'" type="danger" size="small">难</el-tag>
                    <el-tag v-else-if="row.diff === 'mid'" type="warning" size="small">中</el-tag>
                    <el-tag v-else type="success" size="small">易</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="关联课程" prop="course" min-width="160" show-overflow-tooltip />
                <el-table-column label="操作" width="130" fixed="right">
                  <template #default="{ row }">
                    <el-button link size="small" type="primary" @click="openQuestionDialog(row)">编辑</el-button>
                    <el-button link size="small" type="danger" @click="removeQuestion(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!filteredQuestions.length" description="题库为空，点击右上角新建题目" :image-size="60" style="margin-top: 12px" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="24">
            <div class="card card-purple">
              <div class="card-title">
                组卷管理
                <el-button size="small" type="primary" :icon="Document" style="margin-left: 12px" @click="openPaperDialog()">新建试卷</el-button>
              </div>
              <el-table :data="paperRows" size="small" style="margin-top: 8px">
                <el-table-column label="试卷名称" min-width="200">
                  <template #default="{ row }">
                    <el-link type="primary" @click="previewPaper(row)">{{ row.name }}</el-link>
                  </template>
                </el-table-column>
                <el-table-column label="关联课程" min-width="130">
                  <template #default="{ row }">
                    <el-tag v-if="row.courseName" size="small" effect="plain">{{ row.courseName }}</el-tag>
                    <span v-else style="color: var(--color-text-tertiary)">—</span>
                  </template>
                </el-table-column>
                <el-table-column label="题数（单/多/判）" width="160" align="center">
                  <template #default="{ row }">
                    {{ row.single }} + {{ row.multi }} + {{ row.judge }}
                    <span style="color: var(--color-text-secondary); margin-left: 4px">= {{ row.single + row.multi + row.judge }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="总分" width="70" align="center" prop="total" />
                <el-table-column label="通关分数线" width="100" align="center">
                  <template #default="{ row }">{{ row.pass }} 分（{{ row.passPct }}%）</template>
                </el-table-column>
                <el-table-column label="发布对象" min-width="150">
                  <template #default="{ row }">
                    <span v-if="row.status === 'published'">
                      {{ row.audience || '—' }}
                      <span v-if="row.audienceCount" style="color: var(--color-text-tertiary)">（{{ row.audienceCount }} 人）</span>
                    </span>
                    <span v-else style="color: var(--color-text-tertiary)">—</span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.status === 'published'" type="success" size="small">已发布</el-tag>
                    <el-tag v-else type="info" size="small" effect="plain">草稿</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="考试人次" width="90" align="center" prop="publishCount" />
                <el-table-column label="操作" width="230" fixed="right">
                  <template #default="{ row }">
                    <el-button link size="small" @click="previewPaper(row)">预览</el-button>
                    <el-button link size="small" type="success" v-if="row.status !== 'published'" @click="openPublishDialog(row)">发布</el-button>
                    <el-button link size="small" type="primary" @click="openPaperDialog(row)">编辑</el-button>
                    <el-button link size="small" type="danger" @click="removePaper(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!paperRows.length" description="暂无试卷" :image-size="60" style="margin-top: 12px" />
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-teal">
              <div class="card-title">考试记录</div>
              <el-table :data="examRecordRows" size="small" style="margin-top: 8px">
                <el-table-column label="时间" prop="time" width="150" />
                <el-table-column label="试卷" prop="paper" min-width="200" />
                <el-table-column label="员工" prop="user" width="140" />
                <el-table-column label="部门" prop="dept" width="120" />
                <el-table-column label="分数" prop="score" width="90" align="center" />
                <el-table-column label="结果" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.passed ? 'success' : 'danger'" size="small">{{ row.passed ? '通过' : '未通过' }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!examRecordRows.length" description="暂无考试记录" :image-size="60" style="margin-top: 12px" />
              <el-pagination
                v-if="examStats.total > examPageSize"
                style="margin-top: 12px; justify-content: flex-end"
                layout="total, prev, pager, next"
                :total="examStats.total"
                :page-size="examPageSize"
                v-model:current-page="examPage"
              />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <!-- ============ 新建/编辑课程弹窗 ============ -->
    <el-dialog v-model="courseDialogVisible" :title="courseForm.id ? '编辑课程' : '新建课程'" width="600px" destroy-on-close>
      <el-form :model="courseForm" label-width="100px">
        <el-form-item label="课程名称" required>
          <el-input v-model="courseForm.name" placeholder="如：《钓鱼邮件识别进阶》" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="课程类型">
              <el-select v-model="courseForm.type" style="width: 100%">
                <el-option label="视频" value="video" />
                <el-option label="图文" value="article" />
                <el-option label="PDF" value="pdf" />
                <el-option label="互动小游戏" value="interactive" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="难度等级">
              <el-select v-model="courseForm.level" style="width: 100%">
                <el-option label="初级" value="easy" />
                <el-option label="中级" value="mid" />
                <el-option label="高级" value="hard" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="课程时长">
              <el-input-number v-model="courseForm.duration" :min="5" :max="240" :step="5" />
              <span style="margin-left: 8px; color: var(--color-text-secondary); font-size: 12px">分钟</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="课件形态">
              <el-input v-model="courseForm.material" placeholder="如：视频课件 / 图文+PDF" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="课程封面">
          <div class="upload-row">
            <el-upload
              :show-file-list="false"
              accept=".png,.jpg,.jpeg,.webp,.gif"
              :http-request="(opt: any) => handleFileUpload(opt, 'cover')"
            >
              <el-button size="small" :icon="UploadFilled">上传封面图</el-button>
            </el-upload>
            <span v-if="courseForm.cover_url" class="upload-info">
              <el-link type="success" :href="courseForm.cover_url" target="_blank">已上传封面</el-link>
              <el-button link type="danger" size="small" @click="courseForm.cover_url = ''">移除</el-button>
            </span>
            <span v-else class="upload-info dim">建议 800×450，≤2MB（png/jpg/webp）</span>
          </div>
        </el-form-item>
        <el-form-item label="课件文件">
          <div class="upload-row">
            <el-upload
              :show-file-list="false"
              accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.mp4,.webm,.mov,.mp3,.wav"
              :http-request="(opt: any) => handleFileUpload(opt, 'content')"
            >
              <el-button size="small" :icon="UploadFilled">上传课件</el-button>
            </el-upload>
            <span v-if="courseForm.content_url" class="upload-info">
              <el-link type="primary" :href="courseForm.content_url" target="_blank">打开课件</el-link>
              <el-button link type="danger" size="small" @click="courseForm.content_url = ''">移除</el-button>
            </span>
            <span v-else class="upload-info dim">文档/视频/音频，≤100MB</span>
          </div>
        </el-form-item>
        <el-form-item label="课程描述">
          <el-input v-model="courseForm.desc" type="textarea" :rows="3" placeholder="课程目标、适用人群、内容简介" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="courseDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCourse">保存</el-button>
      </template>
    </el-dialog>

    <!-- ============ 课程预览弹窗（视频/PDF 内嵌播放） ============ -->
    <el-dialog v-model="coursePreviewVisible" title="课程详情" :width="isPreviewVideo ? '760px' : '560px'">
      <div v-if="coursePreview" class="preview-body">
        <div class="preview-title">{{ coursePreview.title }}</div>
        <div class="preview-meta">
          <el-tag size="small">{{ courseTypeLabel[coursePreview.type] || coursePreview.type }}</el-tag>
          <el-tag size="small" :type="levelTagType(coursePreview.level)" effect="plain">{{ levelLabel(coursePreview.level) }}</el-tag>
          <span>时长 {{ coursePreview.duration }} 分钟</span>
          <span>课件：{{ coursePreview.material || '未指定' }}</span>
        </div>
        <template v-if="coursePreview.content_url">
          <div v-if="isPreviewVideo" class="preview-media">
            <video
              :src="coursePreview.content_url"
              :poster="coursePreview.cover_url || ''"
              controls
              autoplay
              style="width: 100%; max-height: 420px; background: #000"
            >您的浏览器不支持视频播放，请
              <a :href="coursePreview.content_url" target="_blank">下载课件</a>。
            </video>
          </div>
          <div v-else-if="isPreviewPdf" class="preview-media">
            <iframe :src="coursePreview.content_url" style="width: 100%; height: 480px; border: none; border-radius: 8px" />
          </div>
          <div v-else class="preview-doc">
            <el-alert type="info" :closable="false" show-icon
              title="该课件为文档/音频，浏览器不内嵌预览" description="点击下方按钮在浏览器中打开" />
            <el-button tag="a" type="primary" :href="coursePreview.content_url" target="_blank" style="margin-top: 12px">
              打开课件
            </el-button>
          </div>
        </template>
        <el-alert v-else-if="coursePreview.type === 'video'" type="warning" :closable="false" show-icon
          title="该视频课程尚未上传课件文件" description="请在编辑弹窗上传视频后即可在线观看" style="margin-bottom: 12px" />
        <div v-if="coursePreview.description" class="preview-desc">{{ coursePreview.description }}</div>
        <el-empty v-else-if="!coursePreview.content_url" description="暂无课程描述" :image-size="48" />
      </div>
    </el-dialog>

    <!-- ============ 新建/编辑题目弹窗 ============ -->
    <el-dialog v-model="questionDialogVisible" :title="questionForm.id ? '编辑题目' : '新建题目'" width="640px" destroy-on-close>
      <el-form :model="questionForm" label-width="80px">
        <el-row :gutter="12">
          <el-col :span="10">
            <el-form-item label="题型">
              <el-select v-model="questionForm.type" style="width: 100%" @change="onQuestionTypeChange">
                <el-option label="单选" value="single" />
                <el-option label="多选" value="multi" />
                <el-option label="判断" value="judge" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="7">
            <el-form-item label="难度">
              <el-select v-model="questionForm.diff" style="width: 100%">
                <el-option label="易" value="easy" />
                <el-option label="中" value="mid" />
                <el-option label="难" value="hard" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="7">
            <el-form-item label="课程">
              <el-select v-model="questionForm.course_id" style="width: 100%" clearable placeholder="可空">
                <el-option v-for="c in courses" :key="c.id" :label="c.title" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="题干" required>
          <el-input v-model="questionForm.content" type="textarea" :rows="2" placeholder="输入题目内容" />
        </el-form-item>
        <el-form-item v-if="questionForm.type !== 'judge'" label="选项" required>
          <div class="opt-list">
            <div v-for="(opt, i) in questionForm.options" :key="i" class="opt-row">
              <el-tag size="small">{{ String.fromCharCode(65 + i) }}</el-tag>
              <el-input v-model="questionForm.options[i]" size="small" placeholder="选项内容" style="flex: 1" />
              <el-button link type="danger" :disabled="questionForm.options.length <= 2" @click="questionForm.options.splice(i, 1)">删除</el-button>
            </div>
            <el-button size="small" @click="questionForm.options.push('')">添加选项</el-button>
          </div>
        </el-form-item>
        <el-form-item v-else label="选项">
          <span style="color: var(--color-text-secondary)">A. 正确　B. 错误</span>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="答案" required>
              <el-input v-model="questionForm.answer" :placeholder="questionForm.type === 'judge' ? 'A 或 B' : '如 A 或 A,B'" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解析">
              <el-input v-model="questionForm.analysis" placeholder="答案解析（可选）" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="questionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveQuestion">保存</el-button>
      </template>
    </el-dialog>

    <!-- ============ 新建/编辑试卷弹窗 ============ -->
    <el-dialog v-model="paperDialogVisible" :title="paperForm.id ? '编辑试卷' : '新建试卷'" width="760px" destroy-on-close>
      <el-form :model="paperForm" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="试卷名称" required>
              <el-input v-model="paperForm.title" placeholder="如：Q3全员信息安全摸底考试" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="分数线">
              <el-input-number v-model="paperForm.pass_score" :min="0" :max="100" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="时长(分)">
              <el-input-number v-model="paperForm.duration_min" :min="5" :max="180" :step="5" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联课程">
          <el-select v-model="paperForm.course_id" placeholder="中招员工将按课程参加本试卷考试（可不选）"
            clearable filterable style="width: 100%">
            <el-option v-for="c in courses" :key="c.id" :label="c.title" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择题目">
          <el-table :data="questionBankForPaper" size="small" max-height="260" @selection-change="onPaperQuestionSelect">
            <el-table-column type="selection" width="42" />
            <el-table-column label="题型" width="70">
              <template #default="{ row }">
                <el-tag size="small">{{ row.type === 'single' ? '单选' : row.type === 'multi' ? '多选' : '判断' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="题干" prop="content" show-overflow-tooltip min-width="300" />
            <el-table-column label="难度" width="70" align="center">
              <template #default="{ row }">{{ row.diff === 'hard' ? '难' : row.diff === 'mid' ? '中' : '易' }}</template>
            </el-table-column>
            <el-table-column label="分值" width="110">
              <template #default="{ row }">
                <el-input-number
                  v-model="row._score"
                  :min="1" :max="20" size="small" controls-position="right"
                  style="width: 90px" :disabled="!paperSelectedIds.includes(row.id)"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-form-item>
        <div v-if="paperForm.questions.length" class="paper-summary">
          已选 {{ paperForm.questions.length }} 题，合计 {{ paperTotalScore }} 分
        </div>
      </el-form>
      <template #footer>
        <el-button @click="paperDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePaper">保存</el-button>
      </template>
    </el-dialog>

    <!-- ============ 试卷预览弹窗 ============ -->
    <el-dialog v-model="paperPreviewVisible" title="试卷预览（管理端含答案）" width="720px">
      <template v-if="paperPreview">
        <div class="preview-title">{{ paperPreview.name }}</div>
        <div class="preview-meta">
          <span>共 {{ paperPreview.questions.length }} 题 · 总分 {{ paperPreview.total }} 分</span>
          <span>分数线 {{ paperPreview.pass }} 分</span>
          <span>限时 {{ paperPreview.duration }} 分钟</span>
          <span v-if="paperPreview.audience_label">发布对象：{{ paperPreview.audience_label }}</span>
          <el-tag v-if="paperPreview.status === 'published'" type="success" size="small">已发布</el-tag>
          <el-tag v-else size="small" effect="plain">草稿</el-tag>
        </div>
        <div v-for="(q, i) in paperPreview.questions" :key="q.id" class="paper-q">
          <div class="paper-q-head">
            <span>{{ i + 1 }}. [{{ q.type === 'single' ? '单选' : q.type === 'multi' ? '多选' : '判断' }}] {{ q.content }}</span>
            <el-tag size="small" effect="plain">{{ q.score }} 分</el-tag>
          </div>
          <div v-if="q.type !== 'judge'" class="paper-q-options">
            <span v-for="(opt, j) in q.options" :key="j">{{ String.fromCharCode(65 + j) }}. {{ fmtOption(opt) }}</span>
          </div>
          <div v-else class="paper-q-options">A. 正确　B. 错误</div>
          <div class="paper-q-answer">
            <el-tag type="success" size="small" effect="plain">答案：{{ q.answer }}</el-tag>
            <span v-if="q.analysis" class="paper-q-analysis">解析：{{ q.analysis }}</span>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- ============ 发布试卷弹窗（指定对象） ============ -->
    <el-dialog v-model="publishDialogVisible" title="发布试卷（指定考试对象）" width="600px" destroy-on-close>
      <template v-if="publishPaperRow">
        <div class="preview-meta" style="margin-bottom: 12px">
          <span>{{ publishPaperRow.name }}</span>
          <span>共 {{ publishPaperRow.single + publishPaperRow.multi + publishPaperRow.judge }} 题 · {{ publishPaperRow.total }} 分</span>
        </div>
        <el-form label-width="110px">
          <el-form-item label="发布对象" required>
            <el-radio-group v-model="publishForm.scope">
              <el-radio-button value="all">全员</el-radio-button>
              <el-radio-button value="dept">按部门</el-radio-button>
              <el-radio-button value="users">按人员</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="publishForm.scope === 'dept'" label="选择部门">
            <div class="dept-tree-box">
              <el-tree
                ref="publishDeptTreeRef"
                :data="deptTreeData"
                show-checkbox
                node-key="id"
                :props="{ label: 'label', children: 'children' }"
                default-expand-all
              />
            </div>
          </el-form-item>
          <el-form-item v-if="publishForm.scope === 'users'" label="选择人员">
            <el-select v-model="publishForm.userIds" multiple filterable style="width: 100%" placeholder="搜索并选择员工">
              <el-option v-for="u in empUsers" :key="u.id" :label="`${u.name}（${u.dept || '未分配'}）`" :value="u.id" />
            </el-select>
          </el-form-item>
        </el-form>
        <el-alert type="info" :closable="false" show-icon :title="publishSummary" />
      </template>
      <template #footer>
        <el-button @click="publishDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doPublishPaper">确认发布</el-button>
      </template>
    </el-dialog>

    <!-- ============ 培训任务弹窗 ============ -->
    <el-dialog v-model="taskDialogVisible" :title="'新建培训任务' + (taskForm.courseId ? '（课程已选定）' : '')" width="640px" destroy-on-close>
      <el-form :model="taskForm" label-width="110px">
        <el-form-item label="任务名称" required>
          <el-input v-model="taskForm.name" placeholder="如：Q3全员安全意识强化任务" />
        </el-form-item>
        <el-form-item label="选择课程" required>
          <el-select v-model="taskForm.courseId" style="width: 100%" placeholder="请选择课程">
            <el-option v-for="c in courses" :key="c.id" :label="c.title" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分配范围" required>
          <el-radio-group v-model="taskForm.scope">
            <el-radio-button value="all">全员</el-radio-button>
            <el-radio-button value="dept">按部门</el-radio-button>
            <el-radio-button value="users">按人员</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="taskForm.scope === 'dept'" label="选择部门">
          <div class="dept-tree-box">
            <el-tree
              ref="deptTreeRef"
              :data="deptTreeData"
              show-checkbox
              node-key="id"
              :props="{ label: 'label', children: 'children' }"
              default-expand-all
            />
          </div>
        </el-form-item>
        <el-form-item v-if="taskForm.scope === 'users'" label="选择人员">
          <el-select v-model="taskForm.userIds" multiple filterable style="width: 100%" placeholder="搜索并选择员工">
            <el-option v-for="u in empUsers" :key="u.id" :label="`${u.name}（${u.dept || '未分配'}）`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期" required>
          <el-date-picker
            v-model="taskForm.deadline"
            type="datetime"
            style="width: 100%"
            placeholder="选择截止日期"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTask">创建任务</el-button>
      </template>
    </el-dialog>

    <!-- ============ 任务详情弹窗 ============ -->
    <el-dialog v-model="taskDetailVisible" :title="taskDetail?.name || '任务详情'" width="760px">
      <template v-if="taskDetail">
        <div class="preview-meta" style="margin-bottom: 12px">
          <span>课程：{{ taskDetail.course }}</span>
          <span>对象：{{ taskDetail.target }}</span>
          <span>截止：{{ taskDetail.deadline }}</span>
          <span>完成：{{ taskDetail.people.filter(p => p.status === 'completed').length }}/{{ taskDetail.people.length }} 人</span>
        </div>
        <el-table :data="taskDetail.people" size="small" max-height="400">
          <el-table-column label="姓名" prop="name" width="140" />
          <el-table-column label="部门" prop="dept" width="140" />
          <el-table-column label="进度" min-width="180">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="8" :color="row.progress >= 100 ? '#10B981' : '#378ADD'" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'learning' ? 'warning' : 'info'" size="small">
                {{ row.status === 'completed' ? '已完成' : row.status === 'learning' ? '学习中' : row.status === 'overdue' ? '已逾期' : '未开始' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="完成时间" prop="completed_at" width="150" />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, Calendar, Collection, Plus, Clock, Document, UploadFilled } from '@element-plus/icons-vue'
import type { ElTree } from 'element-plus'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import { orgApi, trainingApi } from '@/api'

const activeTab = ref('course')
const courseKw = ref('')
const categoryFilter = ref('')
const levelFilter = ref('')
const taskKw = ref('')

// ============ 课程 ============
const accentList = ['blue', 'green', 'orange', 'purple', 'red', 'teal'] as const
const COVER_BY_TYPE: Record<string, { bg: string; icon: string }> = {
  video: { bg: 'linear-gradient(135deg, #378ADD, #1E5FA8)', icon: '🛡️' },
  article: { bg: 'linear-gradient(135deg, #10B981, #059669)', icon: '📧' },
  interactive: { bg: 'linear-gradient(135deg, #F59E0B, #D97706)', icon: '🎯' },
  pdf: { bg: 'linear-gradient(135deg, #8E7CC3, #5B4B8A)', icon: '📕' },
  default: { bg: 'linear-gradient(135deg, #6B7280, #4B5563)', icon: '📘' },
}
interface CourseRow {
  id: number
  title: string
  type: string
  typeLabel: string
  tagType: string
  level: string
  material: string
  duration: number
  learners: number
  completion: number
  description?: string
  cover_url?: string
  content_url?: string
  accent: string
  coverBg: string
  coverIcon: string
}
const courses = ref<CourseRow[]>([])

const courseTypeLabel: Record<string, string> = { video: '视频', article: '图文', pdf: 'PDF', interactive: '互动式' }
const courseTagType: Record<string, string> = { video: 'primary', article: 'success', interactive: 'warning', pdf: 'info' }

const courseStats = computed(() => {
  const s = { total: courses.value.length, video: 0, article: 0, pdf: 0, interactive: 0 }
  for (const c of courses.value) {
    if (c.type in s) s[c.type as keyof typeof s] += 1
  }
  return s
})

const filteredCourses = computed(() => {
  const kw = courseKw.value.trim().toLowerCase()
  return courses.value.filter(c => {
    if (categoryFilter.value && c.type !== categoryFilter.value) return false
    if (levelFilter.value && c.level !== levelFilter.value) return false
    if (kw && !c.title.toLowerCase().includes(kw)) return false
    return true
  })
})

async function loadCourses() {
  try {
    const list = (await trainingApi.courses()) as Array<Record<string, any>>
    if (Array.isArray(list)) {
      courses.value = list.map((c, i) => {
        const cover = COVER_BY_TYPE[c.type] ?? COVER_BY_TYPE.default
        return {
          ...c,
          typeLabel: courseTypeLabel[c.type] ?? c.type,
          tagType: courseTagType[c.type] ?? 'primary',
          accent: accentList[i % accentList.length],
          coverBg: cover.bg,
          coverIcon: cover.icon,
        } as CourseRow
      })
    }
  } catch { /* 拦截器已提示 */ }
}

// 课程弹窗（新建/编辑）
const courseDialogVisible = ref(false)
const courseForm = reactive({
  id: 0, name: '', type: 'video', level: 'easy', duration: 20, desc: '', material: '',
  cover_url: '', content_url: '',
})
function openCourseDialog(c?: CourseRow) {
  Object.assign(courseForm, c
    ? { id: c.id, name: c.title, type: c.type, level: c.level, duration: c.duration, desc: '', material: c.material || '', cover_url: '', content_url: '' }
    : { id: 0, name: '', type: 'video', level: 'easy', duration: 20, desc: '', material: '', cover_url: '', content_url: '' })
  if (c) {
    trainingApi.courseDetail(c.id).then((d: any) => {
      if (d?.description) courseForm.desc = d.description
      courseForm.cover_url = d?.cover_url || ''
      courseForm.content_url = d?.content_url || ''
    }).catch(() => { /* 拦截器已提示 */ })
  }
  courseDialogVisible.value = true
}
async function handleFileUpload(opt: { file: File }, fileType: 'cover' | 'content') {
  try {
    const r = await trainingApi.uploadCourseFile(opt.file, fileType)
    if (fileType === 'cover') courseForm.cover_url = r.url
    else courseForm.content_url = r.url
    ElMessage.success(fileType === 'cover' ? '封面已上传' : '课件已上传')
  } catch { /* 拦截器已提示 */ }
}
async function saveCourse() {
  if (!courseForm.name) { ElMessage.warning('请填写课程名称'); return }
  try {
    if (courseForm.id) {
      await trainingApi.updateCourse(courseForm.id, { ...courseForm })
      ElMessage.success('课程已更新')
    } else {
      await trainingApi.createCourse({ ...courseForm })
      ElMessage.success('课程已创建')
    }
    courseDialogVisible.value = false
    loadCourses()
  } catch { /* 拦截器已提示 */ }
}

// 课程预览
const coursePreviewVisible = ref(false)
const coursePreview = ref<CourseRow | null>(null)
const isPreviewVideo = computed(() => /\.(mp4|webm|mov|ogg)$/i.test(coursePreview.value?.content_url || ''))
const isPreviewPdf = computed(() => /\.pdf$/i.test(coursePreview.value?.content_url || ''))
async function previewCourse(c: CourseRow) {
  try {
    const detail = (await trainingApi.courseDetail(c.id)) as any
    coursePreview.value = { ...c, ...(detail || {}) }
  } catch { /* 拦截器已提示 */ }
  coursePreviewVisible.value = true
}

async function removeCourse(c: CourseRow) {
  try {
    await ElMessageBox.confirm(`确认删除课程「${c.title}」？被题目/任务引用时将被拒绝。`, '删除课程', { type: 'warning' })
  } catch { return }
  try {
    await trainingApi.deleteCourse(c.id)
    ElMessage.success('课程已删除')
    loadCourses()
  } catch { /* 拦截器已提示 */ }
}

// ============ 培训任务 ============
interface TaskRow {
  id: number
  name: string; course: string; target: string; count: number
  start: string; end: string; progress: number; started: number; done: number; status: string
}
const taskRows = ref<TaskRow[]>([])

const taskStats = computed(() => {
  const s = { running: 0, completed: 0, totalPeople: 0 }
  for (const t of taskRows.value) {
    if (t.status === 'running' || t.status === 'expired') s.running += 1
    else s.completed += 1
    s.totalPeople += t.count
  }
  return s
})
const filteredTasks = computed(() => {
  const kw = taskKw.value.trim().toLowerCase()
  return taskRows.value.filter(t => !kw || t.name.toLowerCase().includes(kw))
})

async function loadTasks() {
  try {
    const list = (await trainingApi.tasks()) as Array<Record<string, any>>
    if (Array.isArray(list)) taskRows.value = list as TaskRow[]
  } catch { /* 拦截器已提示 */ }
}

// 任务弹窗
const taskDialogVisible = ref(false)
const deptTreeData = ref<{ id: number; label: string; children?: any[] }[]>([])
const deptTreeRef = ref<InstanceType<typeof ElTree>>()
const empUsers = ref<{ id: number; name: string; dept: string }[]>([])
const taskForm = reactive({
  name: '',
  courseId: null as number | null,
  scope: 'all',
  userIds: [] as number[],
  deadline: '' as string,
})

const openTaskDialog = (courseId?: number) => {
  Object.assign(taskForm, { name: '', courseId: courseId ?? null, scope: 'all', userIds: [], deadline: '' })
  loadEmpUsers()
  taskDialogVisible.value = true
}

async function loadEmpUsers() {
  try {
    if (!deptTreeData.value.length) deptTreeData.value = (await orgApi.deptTree()) as any[]
    if (!empUsers.value.length) {
      // pageSize 有后端上限，按页循环拉全量
      const users: { id: number; name: string; dept: string }[] = []
      let page = 1
      let total = 1
      while (users.length < total && page <= 20) {
        const res = (await orgApi.users({ page, pageSize: 100 })) as { total: number; list: { id: number; name: string; dept: string }[] }
        total = res.total || 0
        users.push(...(res.list || []))
        page += 1
      }
      empUsers.value = users
    }
  } catch { /* 拦截器已提示 */ }
}

async function saveTask() {
  if (!taskForm.name) { ElMessage.warning('请填写任务名称'); return }
  if (!taskForm.courseId) { ElMessage.warning('请选择课程'); return }
  if (!taskForm.deadline) { ElMessage.warning('请选择截止日期'); return }
  let targets: Record<string, unknown> = {}
  let labels: string[] = []
  if (taskForm.scope === 'all') {
    targets = { all: true }
    labels = ['全员']
  } else if (taskForm.scope === 'dept') {
    const checked = deptTreeRef.value?.getCheckedNodes(true) ?? []
    const ids = checked.map((n: any) => n.id)
    if (!ids.length) { ElMessage.warning('请选择部门'); return }
    targets = { dept_ids: ids }
    labels = checked.map((n: any) => n.label)
  } else {
    if (!taskForm.userIds.length) { ElMessage.warning('请选择人员'); return }
    targets = { user_ids: taskForm.userIds }
    labels = empUsers.value.filter(u => taskForm.userIds.includes(u.id)).map(u => u.name)
  }
  try {
    await trainingApi.createTask({
      name: taskForm.name,
      courseId: taskForm.courseId,
      deadline: taskForm.deadline,
      targets: { ...targets, labels },
    })
    taskDialogVisible.value = false
    ElMessage.success('培训任务已创建')
    loadTasks()
  } catch { /* 拦截器已提示 */ }
}

// 任务详情 / 催办 / 关闭 / 删除 / 导出
const taskDetailVisible = ref(false)
const taskDetail = ref<{ name: string; course: string; target: string; deadline: string; people: any[] } | null>(null)
async function viewTaskDetail(row: TaskRow) {
  try {
    taskDetail.value = (await trainingApi.taskDetail(row.id)) as any
    taskDetailVisible.value = true
  } catch { /* 拦截器已提示 */ }
}

async function remindTask(row: TaskRow) {
  try {
    const r = (await trainingApi.remindTask(row.id)) as { undone: number }
    ElMessage.success(`催办已发出，尚有 ${r.undone} 人未完成（通知渠道二期接入）`)
  } catch { /* 拦截器已提示 */ }
}

async function closeTask(row: TaskRow) {
  try {
    await ElMessageBox.confirm(`确认关闭任务「${row.name}」？未完成人员明细将保留。`, '关闭任务', { type: 'warning' })
  } catch { return }
  try {
    await trainingApi.closeTask(row.id)
    ElMessage.success('任务已关闭')
    loadTasks()
  } catch { /* 拦截器已提示 */ }
}

async function removeTask(row: TaskRow) {
  try {
    await ElMessageBox.confirm(`确认删除任务「${row.name}」？人员学习明细将一并删除。`, '删除任务', { type: 'warning' })
  } catch { return }
  try {
    await trainingApi.deleteTask(row.id)
    ElMessage.success('任务已删除')
    loadTasks()
  } catch { /* 拦截器已提示 */ }
}

function exportTask(row: TaskRow) {
  trainingApi.exportTask(row.id)
}

// ============ 题库 ============
interface QuestionRow {
  id: number
  type: string; content: string; options: string; diff: string; course: string
}
const questionRows = ref<QuestionRow[]>([])

const questionKw = ref('')
const filteredQuestions = computed(() => {
  const kw = questionKw.value.trim().toLowerCase()
  if (!kw) return questionRows.value
  return questionRows.value.filter(q => q.content.toLowerCase().includes(kw))
})

async function loadQuestionBank() {
  try {
    const list = (await trainingApi.questionBank()) as Array<Record<string, any>>
    if (Array.isArray(list)) {
      questionRows.value = list.map(q => ({
        ...q,
        options: Array.isArray(q.options) ? q.options.join(' / ') : q.options,
      })) as QuestionRow[]
    }
  } catch { /* 拦截器已提示 */ }
}

const questionDialogVisible = ref(false)
const questionForm = reactive({
  id: 0, type: 'single', content: '', options: ['', ''] as string[],
  answer: '', diff: 'easy', analysis: '', course_id: null as number | null,
})
function openQuestionDialog(q?: QuestionRow) {
  if (q) {
    Object.assign(questionForm, {
      id: q.id, type: q.type, content: q.content,
      options: q.type === 'judge' ? [] : (q.options || '').split(' / ').filter(Boolean).map(fmtOption),
      answer: '', diff: q.diff, analysis: '', course_id: null,
    })
    // 回填答案/解析/课程
    loadQuestionMeta(q.id)
  } else {
    Object.assign(questionForm, { id: 0, type: 'single', content: '', options: ['', ''], answer: '', diff: 'easy', analysis: '', course_id: null })
  }
  questionDialogVisible.value = true
}
async function loadQuestionMeta(id: number) {
  try {
    const q = (await trainingApi.questionDetail(id)) as any
    if (q) {
      questionForm.answer = q.answer || ''
      questionForm.analysis = q.analysis || ''
      questionForm.course_id = q.course_id ?? null
    }
  } catch { /* 拦截器已提示 */ }
}
function onQuestionTypeChange() {
  if (questionForm.type === 'judge') {
    questionForm.options = []
    questionForm.answer = 'A'
  } else if (!questionForm.options.length || questionForm.options.length < 2) {
    questionForm.options = ['', '']
    questionForm.answer = ''
  }
}
async function saveQuestion() {
  if (!questionForm.content) { ElMessage.warning('请填写题干'); return }
  const payload: Record<string, unknown> = {
    type: questionForm.type,
    content: questionForm.content,
    answer: questionForm.answer.trim(),
    diff: questionForm.diff,
    analysis: questionForm.analysis,
    course_id: questionForm.course_id,
  }
  if (questionForm.type !== 'judge') {
    const options = questionForm.options.map(o => o.trim()).filter(Boolean)
    if (options.length < 2) { ElMessage.warning('至少提供 2 个选项'); return }
    payload.options = options
  }
  try {
    if (questionForm.id) {
      await trainingApi.updateQuestion(questionForm.id, payload)
      ElMessage.success('题目已更新')
    } else {
      await trainingApi.createQuestion(payload)
      ElMessage.success('题目已创建')
    }
    questionDialogVisible.value = false
    loadQuestionBank()
  } catch { /* 拦截器已提示 */ }
}

async function removeQuestion(q: QuestionRow) {
  try {
    await ElMessageBox.confirm('确认删除该题目？被试卷引用时将被拒绝。', '删除题目', { type: 'warning' })
  } catch { return }
  try {
    await trainingApi.deleteQuestion(q.id)
    ElMessage.success('题目已删除')
    loadQuestionBank()
  } catch { /* 拦截器已提示 */ }
}

// ============ 试卷 ============
interface PaperRow {
  id: number
  name: string; single: number; multi: number; judge: number; total: number
  pass: number; passPct: number; publishCount: number; status: string
  audience?: string; audienceCount?: number
  courseId?: number | null; courseName?: string
}
const paperRows = ref<PaperRow[]>([])

async function loadPapers() {
  try {
    const list = (await trainingApi.papers()) as Array<Record<string, any>>
    if (Array.isArray(list)) paperRows.value = list as PaperRow[]
  } catch { /* 拦截器已提示 */ }
}

const paperDialogVisible = ref(false)
const paperForm = reactive({
  id: 0, title: '', pass_score: 60, duration_min: 30, course_id: undefined as number | undefined,
  questions: [] as { id: number; score: number }[],
})
const questionBankForPaper = ref<{ id: number; type: string; content: string; diff: string; _score: number }[]>([])
const paperSelectedIds = ref<number[]>([])
const paperTotalScore = computed(() => paperForm.questions.reduce((s, q) => s + q.score, 0))

function openPaperDialog(p?: PaperRow) {
  Object.assign(paperForm, p
    ? { id: p.id, title: p.name, pass_score: p.pass, duration_min: 30,
        course_id: p.courseId ?? undefined, questions: [] }
    : { id: 0, title: '', pass_score: 60, duration_min: 30, course_id: undefined, questions: [] })
  paperSelectedIds.value = []
  paperDialogVisible.value = true
  loadPaperQuestionBank()
  if (p) loadPaperQuestions(p.id)
}

async function loadPaperQuestionBank() {
  try {
    const list = (await trainingApi.questionBank()) as any[]
    if (Array.isArray(list)) {
      questionBankForPaper.value = list.map((q: any) => ({
        id: q.id, type: q.type, content: q.content,
        diff: q.diff, _score: 5,
      }))
    }
  } catch { /* 拦截器已提示 */ }
}

async function loadPaperQuestions(pid: number) {
  try {
    const detail = (await trainingApi.paperDetail(pid)) as { questions: { id: number; score: number }[]; duration: number }
    if (detail) {
      paperForm.questions = (detail.questions || []).map(q => ({ id: q.id, score: q.score }))
      paperSelectedIds.value = paperForm.questions.map(q => q.id)
      if (detail.duration) paperForm.duration_min = detail.duration
      for (const q of questionBankForPaper.value) {
        const found = paperForm.questions.find(x => x.id === q.id)
        if (found) q._score = found.score
      }
    }
  } catch { /* 拦截器已提示 */ }
}

function onPaperQuestionSelect(rows: any[]) {
  paperSelectedIds.value = rows.map(r => r.id)
  const map = new Map(rows.map(r => [r.id, r._score]))
  paperForm.questions = rows.map(r => ({ id: r.id, score: Number(map.get(r.id)) || 5 }))
}

async function savePaper() {
  if (!paperForm.title) { ElMessage.warning('请填写试卷名称'); return }
  if (!paperForm.questions.length) { ElMessage.warning('请至少选择一道题目'); return }
  try {
    if (paperForm.id) {
      await trainingApi.updatePaper(paperForm.id, {
        title: paperForm.title,
        pass_score: paperForm.pass_score,
        duration_min: paperForm.duration_min,
        course_id: paperForm.course_id || null,
        questions: paperForm.questions,
      })
      ElMessage.success('试卷已更新')
    } else {
      await trainingApi.createPaper({
        title: paperForm.title,
        pass_score: paperForm.pass_score,
        duration_min: paperForm.duration_min,
        course_id: paperForm.course_id || undefined,
        questions: paperForm.questions,
      })
      ElMessage.success('试卷已创建')
    }
    paperDialogVisible.value = false
    loadPapers()
  } catch { /* 拦截器已提示 */ }
}

// 试卷预览
const paperPreviewVisible = ref(false)
const paperPreview = ref<any>(null)
async function previewPaper(p: PaperRow) {
  try {
    paperPreview.value = await trainingApi.paperDetail(p.id)
    paperPreviewVisible.value = true
  } catch { /* 拦截器已提示 */ }
}

// 发布试卷（指定对象：全员/部门/人员，人群快照入库，供二期学员端分发）
const publishDialogVisible = ref(false)
const publishPaperRow = ref<PaperRow | null>(null)
const publishDeptTreeRef = ref<InstanceType<typeof ElTree>>()
const publishForm = reactive({ scope: 'all', userIds: [] as number[] })
const publishSummary = computed(() => {
  if (!publishPaperRow.value) return ''
  if (publishForm.scope === 'all') return '发布对象：全员'
  if (publishForm.scope === 'dept') {
    const checked = publishDeptTreeRef.value?.getCheckedNodes(true) ?? []
    return checked.length ? `发布对象：${checked.map((n: any) => n.label).join('、')}` : '请选择部门'
  }
  const picked = empUsers.value.filter(u => publishForm.userIds.includes(u.id))
  return picked.length ? `发布对象：${picked.map(u => u.name).join('、')}（${publishForm.userIds.length} 人）` : '请选择人员'
})
function openPublishDialog(row: PaperRow) {
  publishPaperRow.value = row
  Object.assign(publishForm, { scope: 'all', userIds: [] })
  loadEmpUsers()
  publishDialogVisible.value = true
}
async function doPublishPaper() {
  if (!publishPaperRow.value) return
  let audience: Record<string, unknown> = {}
  let labels: string[] = []
  if (publishForm.scope === 'all') {
    audience = { all: true }
    labels = ['全员']
  } else if (publishForm.scope === 'dept') {
    const checked = publishDeptTreeRef.value?.getCheckedNodes(true) ?? []
    const ids = checked.map((n: any) => n.id)
    if (!ids.length) { ElMessage.warning('请选择部门'); return }
    audience = { dept_ids: ids }
    labels = checked.map((n: any) => n.label)
  } else {
    if (!publishForm.userIds.length) { ElMessage.warning('请选择人员'); return }
    audience = { user_ids: publishForm.userIds }
    labels = empUsers.value.filter(u => publishForm.userIds.includes(u.id)).map(u => u.name)
  }
  try {
    const r = await trainingApi.publishPaper(publishPaperRow.value.id, { ...audience, labels })
    publishDialogVisible.value = false
    ElMessage.success(`试卷已发布，覆盖 ${r.count} 名员工`)
    loadPapers()
  } catch { /* 拦截器已提示 */ }
}

async function removePaper(row: PaperRow) {
  try {
    await ElMessageBox.confirm(`确认删除试卷「${row.name}」？考试记录将保留。`, '删除试卷', { type: 'warning' })
  } catch { return }
  try {
    await trainingApi.deletePaper(row.id)
    ElMessage.success('试卷已删除')
    loadPapers()
  } catch { /* 拦截器已提示 */ }
}

// ============ 考试记录 ============
const examRecordRows = ref<{ id: number; time: string; paper: string; user: string; dept: string; score: number; passed: boolean }[]>([])
const examPage = ref(1)
const examPageSize = 10
const examTotal = ref(0)
const examMonthTotal = ref(0)
const examStats = computed(() => ({
  monthTotal: examMonthTotal.value,
  total: examTotal.value,
}))

async function loadExamRecords() {
  try {
    const res = (await trainingApi.examRecords({ page: examPage.value, pageSize: examPageSize })) as any
    if (res) {
      examRecordRows.value = res.list || []
      examTotal.value = res.total || 0
      examMonthTotal.value = res.monthTotal || 0
    }
  } catch { /* 拦截器已提示 */ }
}

// ============ 工具 ============
function levelLabel(level: string) {
  return level === 'easy' ? '初级' : level === 'mid' ? '中级' : '高级'
}
/** 选项文本可能自带 "A." 前缀（seed 数据），展示时统一剥掉由界面拼字母 */
function fmtOption(opt: string) {
  return opt.replace(/^[A-Z][.、]\s*/, '')
}
function levelTagType(level: string) {
  return level === 'easy' ? 'success' : level === 'mid' ? 'warning' : 'danger'
}

onMounted(() => {
  loadCourses()
  loadTasks()
  loadQuestionBank()
  loadPapers()
  loadExamRecords()
})

watch(examPage, () => loadExamRecords())
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.course-card {
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
  }
}
.course-cover {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.cover-icon {
  font-size: 48px;
  opacity: 0.9;
}
.cover-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  width: 100%;
}
.upload-info {
  font-size: 12px;
  color: var(--color-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.upload-info.dim {
  color: var(--color-text-tertiary);
}
.cover-tag {
  position: absolute;
  top: 10px;
  right: 10px;
}
.course-body {
  padding: 12px 14px 14px;
}
.course-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}
.course-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  flex-wrap: wrap;
  .el-icon { vertical-align: middle; margin-right: 2px; }
}
.course-stats {
  display: flex;
  padding: 10px;
  background: var(--color-background-secondary);
  border-radius: 8px;
  margin-bottom: 10px;
}
.stat {
  flex: 1;
  text-align: center;
  &:not(:last-child) { border-right: 1px solid var(--color-border-tertiary); }
}
.stat-val {
  font-size: 16px;
  font-weight: 600;
}
.stat-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.course-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}
.task-progress {
  .progress-detail {
    font-size: 11px;
    color: var(--color-text-tertiary);
    margin-top: 4px;
  }
}
.opt-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.opt-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.paper-summary {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
.preview-body {
  .preview-title { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
  .preview-meta {
    display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px;
    color: var(--color-text-secondary); margin-bottom: 12px;
  }
  .preview-desc {
    font-size: 13px; color: var(--color-text-primary);
    background: var(--color-background-secondary); border-radius: 8px; padding: 12px;
    line-height: 1.7;
  }
  .preview-media {
    margin-bottom: 12px;
  }
}
.paper-q {
  border-bottom: 1px dashed var(--color-border-tertiary);
  padding: 10px 0;
  .paper-q-head {
    display: flex; justify-content: space-between; gap: 8px;
    font-size: 13px; font-weight: 500;
  }
  .paper-q-options {
    display: flex; flex-direction: column; gap: 4px;
    font-size: 12px; color: var(--color-text-secondary);
    margin: 6px 0;
  }
  .paper-q-answer {
    display: flex; gap: 10px; align-items: center; font-size: 12px;
  }
  .paper-q-analysis {
    color: var(--color-text-tertiary);
  }
}
.dept-tree-box {
  width: 100%;
  max-height: 220px;
  overflow: auto;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  padding: 8px;
}
</style>
